#!/usr/bin/env python

import os, sys
import glob
import optparse
import copy
import time
import h5py
import json
from functools import reduce

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
font = {'size'   : 22}
matplotlib.rc('font', **font)
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import LogNorm
from matplotlib.colors import Normalize

import astropy
from astropy.table import Table, vstack
from astropy.time import Time
from astropy.coordinates import Angle
from astropy.io import ascii
from astropy import units as u
from astropy.coordinates import SkyCoord

from panoptes_client import Panoptes, Project, SubjectSet, Subject, Workflow

from ztfperiodic.utils import convert_to_hex
from ztfperiodic.utils import get_kowalski
from ztfperiodic.utils import get_kowalski_features_objids 
from ztfperiodic.utils import get_kowalski_classifications_objids
from ztfperiodic.utils import get_kowalski_objids
from ztfperiodic.utils import gaia_query
from ztfperiodic.utils import combine_lcs
from ztfperiodic.zooniverse import ZooProject

try:
    from penquins import Kowalski
except:
    print("penquins not installed... need to use matchfiles.")

def parse_commandline():
    """
    Parse the options given on the command-line.
    """
    parser = optparse.OptionParser()
    parser.add_option("--doPlots",  action="store_true", default=False)
    parser.add_option("--doLCFile",  action="store_true", default=False)
    parser.add_option("--doFakeData",  action="store_true", default=False)

    parser.add_option("-o","--outputDir",default="/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/top_sources")
    #parser.add_option("-o","--outputDir",default="/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2_ids_DR2/catalog/compare/rrlyr/")
    parser.add_option("-c","--catalogPath",default="/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/slices/d11.pnp.f.h5")

    parser.add_option("--doDifference",  action="store_true", default=False)
    parser.add_option("-d","--differencePath",default="/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/slices/d11.dscu.f.h5,/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/slices/d11.rrlyr.f.h5,/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/slices/d11.ea.f.h5,/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/slices/d11.eb.f.h5,/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/slices/d11.ew.f.h5")

    parser.add_option("--doIntersection",  action="store_true", default=False)
    parser.add_option("-i","--intersectionPath",default="/home/michael.coughlin/ZTF/output_features_20Fields_ids_DR2/catalog/compare/slices/d11.ceph.f.h5")

    parser.add_option("-u","--user")
    parser.add_option("-w","--pwd")

    parser.add_option("--doSubjectSet",  action="store_true", default=False)
    parser.add_option("--zooniverse_user")
    parser.add_option("--zooniverse_pwd")
    parser.add_option("--zooniverse_id",default=4878,type=int)

    parser.add_option("-N","--Nexamples",default=10,type=int)

    opts, args = parser.parse_args()

    return opts

# Parse command line
opts = parse_commandline()

outputDir = opts.outputDir
catalogPath = opts.catalogPath
differencePath = opts.differencePath   
intersectionPath = opts.intersectionPath

if ".h5" in catalogPath:
    intersectionType = intersectionPath.split("/")[-1].replace(".h5","")
elif ".fits" in catalogPath:
    intersectionType = intersectionPath.split("/")[-1].replace(".fits","")
elif ".csv" in catalogPath:
    intersectionType = catalogPath.split("/")[-1].replace(".csv","")

outputDir = os.path.join(outputDir, intersectionType)

plotDir = os.path.join(outputDir,'plots')
if not os.path.isdir(plotDir):
    os.makedirs(plotDir)

jsonDir = os.path.join(outputDir,'json')
if not os.path.isdir(jsonDir):
    os.makedirs(jsonDir)

scriptpath = os.path.realpath(__file__)
inputDir = os.path.join("/".join(scriptpath.split("/")[:-2]),"input")

WDcat = os.path.join(inputDir,'GaiaHRSet.hdf5')
with h5py.File(WDcat, 'r') as f:
    gmag, bprpWD = f['gmag'][:], f['bp_rp'][:]
    parallax = f['parallax'][:]
absmagWD=gmag+5*(np.log10(np.abs(parallax))-2)
 
kow = []
nquery = 10
cnt = 0
while cnt < nquery:
    try:
        kow = Kowalski(username=opts.user, password=opts.pwd)
        break
    except:
        time.sleep(5)
    cnt = cnt + 1
if cnt == nquery:
    raise Exception('Kowalski connection failed...')

if opts.doSubjectSet:
    zoo = ZooProject(username=opts.zooniverse_user,
                     password=opts.zooniverse_pwd,
                     project_id=opts.zooniverse_id) 

if ".h5" in catalogPath:
    df = pd.read_hdf(catalogPath, 'df')
elif ".fits" in catalogPath:
    tab = Table.read(catalogPath, format='fits')
    df = tab.to_pandas()
    df.set_index('objid',inplace=True)
elif ".csv" in catalogPath:
    tab = Table.read(catalogPath, format='csv')

    objids = []
    for row in tab:
        lightcurves_all = get_kowalski(row["RA"], row["Dec"], kow,
                                       min_epochs=20)
        nmax, key_to_keep = -1, -1
        for ii, key in enumerate(lightcurves_all.keys()):
            lc = lightcurves_all[key]
            if len(lc["fid"]) > nmax:
                nmax, key_to_keep = len(lc["fid"]), key
        objids.append(int(key_to_keep))
    objids = np.array(objids)
    tab["objid"] = objids
    tab.add_index('objid')
    idx = np.where(objids>0)[0]
    tab = tab.iloc[idx]

    df = tab.to_pandas()

if opts.doDifference:
    differenceFiles = differencePath.split(",")
    for differenceFile in differenceFiles:
        df1 = pd.read_hdf(differenceFile, 'df')
        idx = df.index.difference(df1.index)
        df = df.loc[idx]
if opts.doIntersection:
    intersectionFiles = intersectionPath.split(",")
    for intersectionFile in intersectionFiles:
        if ".h5" in catalogPath:
            df1 = pd.read_hdf(intersectionFile, 'df')
        else:
            tab = Table.read(intersectionFile, format='fits')
            df1 = tab.to_pandas()
            df1.set_index('objid',inplace=True)

        idx = df.index.intersection(df1.index)
        df = df.loc[idx]

        idx = df1.index.intersection(df.index)
        df1 = df1.loc[idx]

if opts.doIntersection:
    col = df1.columns[0]
    idx = np.argsort(df1[col])[::-1]
    idx = np.array(idx).astype(int)[:opts.Nexamples]

    idy = df.index.intersection(df1.iloc[idx].index)
    df = df.loc[idy]
    df1 = df1.iloc[idx]

fs = 24
colors = ['g','r','y']
symbols = ['x', 'o', '^']
fids = [1,2,3]
bands = {1: 'g', 2: 'r', 3: 'i'}

if opts.doSubjectSet:
   image_list, metadata_list, subject_set_name = [], [], intersectionType 

objfile = os.path.join(plotDir, 'objids.dat')
objfid = open(objfile, 'w')
for ii, (index, row) in enumerate(df.iterrows()): 
    if np.mod(ii,100) == 0:
        print('Loading %d/%d'%(ii,len(df)))

    if opts.doFakeData:
        nsample = 100
        objid = index
        ra, dec = 10.0, 60.0
        period, amp = 0.5, 1.0
        lightcurves_all = {}
        lightcurves, absmags, bp_rps = [], [], []
        for fid in fids:
            lc = {}
            lc["name"] = bands[fid]
            lc["hjd"] = np.random.uniform(low=0, high=365, size=(nsample,))
            lc["mag"] = np.random.uniform(low=18, high=19, size=(nsample,))
            lc["magerr"] = np.random.uniform(low=0.01, high=0.1, size=(nsample,))           
            lc["fid"] = fid*np.ones(lc["hjd"].shape)
            lc["ra"] = ra*np.ones(lc["hjd"].shape)
            lc["dec"] = dec*np.ones(lc["hjd"].shape)
            lc["absmag"] = [np.nan, np.nan, np.nan]
            lc["bp_rp"] = np.nan
            lc["parallax"] = np.nan

            lightcurves_all[fid] = lc
            lightcurves.append([lc["hjd"], lc["mag"], lc["magerr"]])
            absmags.append(lc["absmag"])
            bp_rps.append(lc["bp_rp"])
 
        lightcurves_combined = combine_lcs(lightcurves_all)
        key = list(lightcurves_combined.keys())[0]

    else:
        objid, features = get_kowalski_features_objids([index], kow)
        if len(features) == 0:
            continue

        period = features.period.values[0]
        amp = features.f1_amp.values[0]
        lightcurves, coordinates, filters, ids, absmags, bp_rps, names, baseline = get_kowalski_objids([index], kow)
        ra, dec = coordinates[0][0], coordinates[0][1]

        lightcurves_all = get_kowalski(ra, dec, kow,
                                       min_epochs=20)
        lightcurves_combined = combine_lcs(lightcurves_all)
        key = list(lightcurves_combined.keys())[0] 

    hjd, magnitude, err = lightcurves[0]
    absmag, bp_rp = absmags[0], bp_rps[0]
    gaia = gaia_query(ra, dec, 5/3600.0)
    d_pc, gofAL = None, None
    if gaia:
        Plx = gaia['Plx'].data.data[0] # mas
        gofAL = gaia["gofAL"].data.data[0]
        # distance in pc
        if Plx > 0 :
            d_pc = 1 / (Plx*1e-3)

    if opts.doLCFile:
        data_json = {}
        data_json["data"] = {}
        data_json["data"]["scatterPlot"] = {}
        data_json["data"]["scatterPlot"]["data"] = []
        data_json["data"]["scatterPlot"]["chartOptions"] = {"xAxisLabel": "Days", "yAxisLabel": "Brightness"}

        data_json["data"]["barCharts"] = {}
        data_json["data"]["barCharts"]["period"] = {}
        data_json["data"]["barCharts"]["period"]["data"] = []
        data_json["data"]["barCharts"]["period"]["chartOptions"] = {"xAxisLabel": "Period", "yAxisLabel": ""}
        data_json["data"]["barCharts"]["amplitude"] = {}
        data_json["data"]["barCharts"]["amplitude"]["data"] = []
        data_json["data"]["barCharts"]["amplitude"]["chartOptions"] = {"xAxisLabel": "Amplitude", "yAxisLabel": ""}        

        periods, amplitudes = [], []
        for jj, (fid, color, symbol) in enumerate(zip(fids, colors, symbols)):
            if fid == 3: continue

            seriesData = []
            nmax, period_tmp, amp_tmp = -1, period, amp
            for ii, key in enumerate(lightcurves_all.keys()):
                lc = lightcurves_all[key]
                if not lc["fid"][0] == fid: continue
                idx = np.where(lc["fid"][0] == fids)[0]

                t0 = lc["hjd"] - Time('2018-01-01T00:00:00', 
                                      format='isot', scale='utc').jd
                for x, y, yerr in zip(lc["hjd"], lc["mag"], lc["magerr"]):
                    data_single = {"x": x, "y": np.median(lc["mag"])-y,
                                   "yerr": yerr}
                    seriesData.append(data_single)
       
                tmp, features = get_kowalski_features_objids([int(key)], kow)
                if len(features) == 0:
                    continue

                if len(lc["fid"]) > nmax:
                    nmax = len(lc["fid"])
                    period_tmp = features.period.values[0]
                    #amp_tmp = features.f1_amp.values[0]
                    amp_tmp = np.diff(np.percentile(lc["mag"], (2.5,97.5)))[0]

            if len(seriesData) == 0: continue

            if fid == 1:
                label, color = "g", "#66CDAA"
            elif fid == 2:
                label, color = "r", "#DC143C"
            elif fid == 3:
                label, color = "i", "#DAA520"

            seriesOptions = {"color": color,
                             "label": label,
                             "period": period_tmp}
            periodOptions = {"color": color,
                             "label": label,
                             "value": np.log10(period_tmp)}
            amplitudeOptions = {"color": color,
                                "label": label,
                                "value": amp_tmp}

            data_json["data"]["scatterPlot"]["data"].append({"seriesData": seriesData, "seriesOptions": seriesOptions})
            data_json["data"]["barCharts"]["period"]["data"].append(periodOptions)
            data_json["data"]["barCharts"]["amplitude"]["data"].append(amplitudeOptions)
 
        photFile = os.path.join(jsonDir,'%d.json' % objid)
        with open(photFile, 'w', encoding='utf-8') as f:
            json.dump(data_json, f, ensure_ascii=False, indent=4)

    if opts.doPlots:
        fig, (ax1, ax2) = plt.subplots(1, 2,figsize=(20,10))
        plt.axes(ax1)
        bands_count = np.zeros((len(fids),1))
        for jj, (fid, color, symbol) in enumerate(zip(fids, colors, symbols)):
            for ii, key in enumerate(lightcurves_all.keys()):
                lc = lightcurves_all[key]
                if not lc["fid"][0] == fid: continue
                idx = np.where(lc["fid"][0] == fids)[0]
                if bands_count[idx] == 0:
                    plt.errorbar(np.mod(lc["hjd"], 2.0*period)/(2.0*period), lc["mag"],yerr=lc["magerr"],fmt='%s%s' % (color,symbol), label=bands[fid])
                else:
                    plt.errorbar(np.mod(lc["hjd"], 2.0*period)/(2.0*period), lc["mag"],yerr=lc["magerr"],fmt='%s%s' % (color,symbol))
                bands_count[idx] = bands_count[idx] + 1
        plt.xlabel('Phase', fontsize = fs)
        plt.ylabel('Magnitude [ab]', fontsize = fs)
        plt.legend(prop={'size': 20})
        ax1.tick_params(axis='both', which='major', labelsize=fs)
        ax1.tick_params(axis='both', which='minor', labelsize=fs)
        ax1.invert_yaxis()
        plt.title("Period = %.3f days"%period, fontsize = fs)

        plt.axes(ax2)
        asymmetric_error = np.atleast_2d([absmag[1], absmag[2]]).T
        hist2 = ax2.hist2d(bprpWD,absmagWD, bins=100,zorder=0,norm=LogNorm())
        if not np.isnan(bp_rp) or not np.isnan(absmag[0]):
            ax2.errorbar(bp_rp,absmag[0],yerr=asymmetric_error,
                         c='r',zorder=1,fmt='o')
        ax2.set_xlim([-1,4.0])
        ax2.set_ylim([-5,18])
        ax2.invert_yaxis()
        cbar = fig.colorbar(hist2[3],ax=ax2)
        cbar.set_label('Object Count')
        ax2.set_xlabel('Gaia BP - RP')
        ax2.set_ylabel('Gaia $M_G$')

        if (not d_pc is None) and (not gofAL is None):
            ax2.set_title("d = %d [pc], gof = %.1f"%(d_pc, gofAL), fontsize = fs)

        plt.tight_layout()
        pngfile = os.path.join(plotDir,'%d.png' % objid)
        fig.savefig(pngfile, bbox_inches='tight')
        plt.close()

        fig = plt.figure(figsize=(10,10))
        ax = plt.gca()
        asymmetric_error = np.atleast_2d([absmag[1], absmag[2]]).T
        hist2 = ax.hist2d(bprpWD,absmagWD, bins=100,zorder=0,norm=LogNorm())
        if not np.isnan(bp_rp) or not np.isnan(absmag[0]):
            ax.errorbar(bp_rp,absmag[0],yerr=asymmetric_error,
                        c='r',zorder=1,fmt='o')
        ax.set_xlim([-1,4.0])
        ax.set_ylim([-5,18])
        ax.invert_yaxis()
        cbar = fig.colorbar(hist2[3],ax=ax)
        cbar.set_label('Object Count')
        ax.set_xlabel('Gaia BP - RP')
        ax.set_ylabel('Gaia $M_G$')

        if (not d_pc is None) and (not gofAL is None):
            ax.set_title("d = %d [pc], gof = %.1f"%(d_pc, gofAL), fontsize = fs)

        plt.tight_layout()
        pngfile_HR = os.path.join(plotDir,'%d_HR.png' % objid)
        fig.savefig(pngfile_HR, bbox_inches='tight')
        plt.close()

    objfid.write('%d %.10f %.10f %.10f\n' % (index, ra, dec, period))
    print('%d %.10f %.10f %.10f' % (index, ra, dec, period))

    if opts.doSubjectSet:
        #image_list.append(pngfile)
        image_list.append({"image_png_1": pngfile, 
                           "application_json": photFile,
                           "image_png_2": pngfile_HR})

        mdict = {'candidate': int(objid),
                 'ra': ra, 'dec': dec, 
                 'period': period}
        metadata_list.append(mdict)
objfid.close()

if opts.doSubjectSet:
    #ret = zoo.add_new_subject(image_list,
    #                          metadata_list,
    #                          subject_set_name=subject_set_name)

    ret = zoo.add_new_subject_timeseries(image_list,
                                         metadata_list,
                                         subject_set_name=subject_set_name)

