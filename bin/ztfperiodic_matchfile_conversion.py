
import os, sys
import glob
import optparse
from pathlib import Path

import tables
import pandas as pd
import numpy as np
import h5py

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.pyplot import cm

def parse_commandline():
    """
    Parse the options given on the command-line.
    """
    parser = optparse.OptionParser()

    parser.add_option("-o","--outputDir",default="/media/Data/mcoughlin/Matchfiles")
    parser.add_option("-p","--plotDir",default="/media/Data/mcoughlin/Matchfiles_plots")
    

    parser.add_option("-d","--dataDir",default="/media/Data2/Matchfiles/ztfweb.ipac.caltech.edu/ztf/ops/srcmatch")
    parser.add_option("-f","--filename",default=None)

    parser.add_option("--doOverwrite",  action="store_true", default=False)
    parser.add_option("--doDetrend",  action="store_true", default=False)
    parser.add_option("--doPlots",  action="store_true", default=False)
    parser.add_option("-n","--nobjects",default=50,type=int)

    opts, args = parser.parse_args()

    return opts

# Parse command line
opts = parse_commandline()

if opts.doDetrend:
    from pdtrend import FMdata, PDTrend

dataDir = opts.dataDir
outputDir = opts.outputDir

plotDir = os.path.join(outputDir,'plots')
if not os.path.isdir(plotDir):
    os.makedirs(plotDir)
catalogDir = os.path.join(outputDir,'catalog')
if not os.path.isdir(catalogDir):
    os.makedirs(catalogDir)

directory="%s/*/*/*"%opts.dataDir

for f in glob.iglob(directory):
    if opts.filename is not None:
        if not opts.filename in f: continue
    fileend = "/".join(f.split("/")[-3:])
    fnew = "%s/%s"%(outputDir,fileend)
    filedir = "/".join(fnew.split("/")[:-1])
    if not os.path.isdir(filedir):
        os.makedirs(filedir)

    pnew =  "%s/%s"%(plotDir,fileend)
    pdir = "/".join(pnew.split("/")[:-1])
    if not os.path.isdir(pdir):
        os.makedirs(pdir)

    cnew =  "%s/%s"%(catalogDir,fileend)
    cdir = "/".join(cnew.split("/")[:-1])
    if not os.path.isdir(cdir):
        os.makedirs(cdir)

    fnew = fnew.replace("pytable","h5")
    pnew = pnew.replace("pytable","png")
    cnew = cnew.replace("pytable","dat")
    if not opts.doOverwrite:
        if os.path.isfile(fnew): continue

    print("Running %s"%fnew)

    with tables.open_file(f) as store:
        for tbl in store.walk_nodes("/", "Table"):
            if tbl.name in ["sourcedata", "transientdata"]:
                group = tbl._v_parent
                break
        srcdata = pd.DataFrame.from_records(store.root.matches.sourcedata.read_where('programid > 1'))
        srcdata.sort_values('matchid', axis=0, inplace=True)
        exposures = pd.DataFrame.from_records(store.root.matches.exposures.read_where('programid > 1'))
        merged = srcdata.merge(exposures, on="expid")

        if len(merged.matchid.unique()) == 0:
            continue

        matchids = np.array(merged.matchid)
        values, indices, counts = np.unique(matchids, return_counts=True,return_inverse=True)       
        idx = np.where(counts>50)[0]

        if len(idx) == 0:
            Path(fnew).touch()
            continue

        f = h5py.File(fnew, 'w')

        matchids, idx2 = np.unique(matchids[idx],return_index=True)
        ncounts = counts[idx][idx2]
        nmatchids = len(idx)

        if opts.doDetrend:
            idx = np.argsort(ncounts)[::-1][:opts.nobjects]
            matchids_weather = matchids[idx]

            cnt = 0
            RAs, Decs, errs, lcs, times, ids = [], [], [], [], [], []
            idx_weather = []
            for ii,k in enumerate(matchids):
                if np.mod(cnt,100) == 0:
                    print('%d/%d'%(cnt,len(matchids)))
                df = merged[merged['matchid'] == k]
                RA, Dec, x, err = df.ra, df.dec, df.psfmag, df.psfmagerr
                obsHJD = df.hjd

                if len(x) < 50: continue

                idx = np.argsort(obsHJD.values)
                errs.append(err.values[idx])
                lcs.append(x.values[idx])
                times.append(obsHJD.values[idx])
                RAs.append(RA.values[0])
                Decs.append(Dec.values[0])
                ids.append(k)

                if k in matchids_weather:
                    idx_weather.append(cnt)

                cnt = cnt + 1

            # Filling missing data points.
            fmt = FMdata(lcs, times, n_min_data=50)
            results = fmt.run()
            lcs = results['lcs']
            epoch = results['epoch']

            lcs_weather = []
            for k in idx_weather:
                lcs_weather.append(lcs[k])

            # Create PDT instance.
            pdt = PDTrend(lcs_weather,dist_cut=0.6,n_min_member=5)
            # Find clusters and then construct master trends.
            pdt.run()

            if opts.doPlots:
                fig = plt.figure(figsize=(30,10))
                ax = fig.add_subplot(1, 1, 1)
                colors=cm.rainbow(np.linspace(0,1,len(lcs)))

            fid = open(cnew,'w')
            cnt = 0
            for obsHJD, x, err, RA, Dec, k in zip(times, lcs, errs, RAs, Decs, ids):
                if np.mod(cnt,100) == 0:
                    print('%d/%d'%(cnt,len(times)))
                vals = np.interp(obsHJD,epoch,pdt.detrend(x))
                data = np.vstack((obsHJD,vals,err))
                key = "%d_%.10f_%.10f"%(k,RA,Dec)
                f.create_dataset(key, data=data, dtype='float64', compression="gzip",shuffle=True)

                fid.write('%.10f %.10f %.10f\n'%(RA,Dec,len(x)/np.max(ncounts)))
                if opts.doPlots:
                    vals = vals - np.median(vals)
                    bins = np.linspace(np.min(vals),np.max(vals),11)
                    hist, bin_edges = np.histogram(vals, bins=bins, density=True)
                    bins = (bin_edges[1:] + bin_edges[:-1])/2.0
                    plt.plot(bins, hist, color = colors[cnt], linestyle='-', drawstyle='steps')

                    x = x - np.median(x)
                    bins = np.linspace(np.min(x),np.max(x),11)
                    hist, bin_edges = np.histogram(x, bins=bins, density=True)
                    bins = (bin_edges[1:] + bin_edges[:-1])/2.0
                    plt.plot(bins, hist, color = colors[cnt], linestyle='--', drawstyle='steps')

                cnt = cnt + 1

            fid.close()
            if opts.doPlots:
                ax.set_yscale('log')
                plt.savefig(pnew)
                plt.close()

        else:

            if opts.doPlots:
                fig = plt.figure(figsize=(30,10))
                ax = fig.add_subplot(1, 1, 1)
                colors=cm.rainbow(np.linspace(0,1,len(matchids)))

            fid = open(cnew,'w')
            cnt = 0
            for k in matchids:
                if np.mod(cnt,100) == 0:
                    print('%d/%d'%(cnt,len(matchids)))
                df = merged[merged['matchid'] == k]
                RA, Dec, x, err = df.ra, df.dec, df.psfmag, df.psfmagerr
                obsHJD = df.hjd
    
                if len(x) < 50: continue
    
                data = np.vstack((obsHJD,x,err))
                key = "%d_%.10f_%.10f"%(k,RA.values[0],Dec.values[0])
                f.create_dataset(key, data=data, dtype='float64', compression="gzip",shuffle=True)

                fid.write('%.10f %.10f %.10f\n'%(RA.values[0],Dec.values[0],len(x)/np.max(ncounts)))

                if opts.doPlots:
                    x = x - np.median(x)
                    bins = np.linspace(np.min(x.values),np.max(x.values),11)
                    hist, bin_edges = np.histogram(x.values, bins=bins, density=True)
                    bins = (bin_edges[1:] + bin_edges[:-1])/2.0
                    plt.plot(bins, hist, color = colors[cnt], linestyle='--', drawstyle='steps')

                cnt = cnt + 1

            fid.close()
            if opts.doPlots:
                ax.set_yscale('log')
                plt.savefig(pnew)
                plt.close()

        f.close()

