
import os, sys
import glob
import optparse

import tables
import pandas as pd
import numpy as np
import h5py

import ztfperiodic.utils

try:
    from penquins import Kowalski
except:
    print("penquins not installed... need to use matchfiles.")

def parse_commandline():
    """
    Parse the options given on the command-line.
    """
    parser = optparse.OptionParser()

    parser.add_option("-p","--python",default="python")

    parser.add_option("--doGPU",  action="store_true", default=False)
    parser.add_option("--doCPU",  action="store_true", default=False)

    parser.add_option("-o","--outputDir",default="/home/mcoughlin/ZTF/output")
    parser.add_option("--matchfileDir",default="/home/mcoughlin/ZTF/matchfiles/")
    parser.add_option("-b","--batch_size",default=1,type=int)
    parser.add_option("-a","--algorithm",default="CE")

    parser.add_option("--doLongPeriod",  action="store_true", default=False)
    parser.add_option("--doCombineFilt",  action="store_true", default=False)
    parser.add_option("--doRemoveHC",  action="store_true", default=False)
    parser.add_option("--doHCOnly",  action="store_true", default=False)
    parser.add_option("--doUsePDot",  action="store_true", default=False)
    parser.add_option("--doSpectra",  action="store_true", default=False)
    parser.add_option("--doQuadrantScale",  action="store_true", default=False)

    parser.add_option("-l","--lightcurve_source",default="Kowalski")
    parser.add_option("-s","--source_type",default="quadrant")
    parser.add_option("--catalog_file",default="../input/xray.dat")
    parser.add_option("--Ncatalog",default=13.0,type=int)
    parser.add_option("--Nmax",default=1000.0,type=int)

    parser.add_option("--doVariability",  action="store_true", default=False)
    parser.add_option("--doCutNObs",  action="store_true", default=False)
    parser.add_option("-n","--NObs",default=50,type=int)

    parser.add_option("--doUseMatchfileFile",  action="store_true", default=False)
    parser.add_option("--doCrossMatch",  action="store_true", default=False)

    parser.add_option("--qid",default=None,type=int)
    parser.add_option("--fid",default=None,type=int)

    parser.add_option("--doDocker",  action="store_true", default=False)
    parser.add_option("--doRsyncFiles",  action="store_true", default=False)

    parser.add_option("--doPercentile",  action="store_true", default=False)
    parser.add_option("--doParallel",  action="store_true", default=False)
    parser.add_option("--doPlots",  action="store_true", default=False)

    parser.add_option("-u","--user")
    parser.add_option("-w","--pwd")

    parser.add_option("--min_epochs",default=50,type=int)

    parser.add_option("-i","--injtype",default="wdb")

    opts, args = parser.parse_args()

    return opts

# Parse command line
opts = parse_commandline()
Ncatalog = opts.Ncatalog
min_epochs = opts.min_epochs
injtype = opts.injtype

if not (opts.doCPU or opts.doGPU):
    print("--doCPU or --doGPU required")
    exit(0)

if opts.doCPU:
    cpu_gpu_flag = "--doCPU"
else:
    cpu_gpu_flag = "--doGPU"

extra_flags = []
if opts.doLongPeriod:
    extra_flags.append("--doLongPeriod")
if opts.doCombineFilt:
    extra_flags.append("--doCombineFilt")
if opts.doRemoveHC:
    extra_flags.append("--doRemoveHC")
if opts.doHCOnly:
    extra_flags.append("--doHCOnly")
if opts.doUsePDot:
    extra_flags.append("--doUsePDot")
if opts.doSpectra:
    extra_flags.append("--doSpectra")
if opts.doVariability:
    extra_flags.append("--doVariability")
    extra_flags.append("--doNotPeriodFind")
if opts.doRsyncFiles:
    extra_flags.append("--doRsyncFiles")
if opts.doCrossMatch:
    extra_flags.append("--doCrossMatch")
if opts.doPercentile:
    extra_flags.append("--doPercentile")
if opts.doParallel:
    extra_flags.append("--doParallel")
if opts.doPlots:
    extra_flags.append("--doPlots")
extra_flags = " ".join(extra_flags)

matchfileDir = opts.matchfileDir
outputDir = opts.outputDir
batch_size = opts.batch_size
algorithm = opts.algorithm

catalogDir = os.path.join(outputDir,'catalog',algorithm.replace(",","_"))

condorDir = os.path.join(outputDir,'condor')
if not os.path.isdir(condorDir):
    os.makedirs(condorDir)

logDir = os.path.join(condorDir,'logs')
if not os.path.isdir(logDir):
    os.makedirs(logDir)

idsDir = os.path.join(condorDir,'ids')
if not os.path.isdir(idsDir):
    os.makedirs(idsDir)
idsDir = "/home/michael.coughlin/ZTF/output_quadrants_Primary_DR3/condor/ids"

if opts.doCutNObs:
    nobsfile = "../input/nobs.dat"
    nobs_data = np.loadtxt(nobsfile)

    if opts.doHCOnly:
        idx = np.where((nobs_data[:,10] >= opts.NObs) | (nobs_data[:,11] >= opts.NObs) | (nobs_data[:,12] >= opts.NObs))[0]
    else:
        idx = np.where((nobs_data[:,7] >= opts.NObs) | (nobs_data[:,8] >= opts.NObs) | (nobs_data[:,9] >= opts.NObs))[0]

    nobs_data = nobs_data[idx,:]
    fields_list = nobs_data[:,0]

dir_path = os.path.dirname(os.path.realpath(__file__))

condordag = os.path.join(condorDir,'condor.dag')
fid = open(condordag,'w') 
condorsh = os.path.join(condorDir,'condor.sh')
fid1 = open(condorsh,'w') 

job_number = 0

if opts.doQuadrantScale:
    kow = Kowalski(username=opts.user, password=opts.pwd)

mag_min, mag_max = 16.0, 21.0
period_min, period_max = 4.0*60.0/86400.0, 60.0*60.0/86400.0
inclination_min, inclination_max = 0.0, 90.0

mags = np.linspace(mag_min, mag_max, 31)
periods = np.linspace(period_min, period_max, 31)
inclinations = np.linspace(inclination_min, inclination_max, 11)

if opts.lightcurve_source == "Kowalski":

    if opts.source_type == "quadrant":
        fields, ccds, quadrants = np.arange(1,880), np.arange(1,17), np.arange(1,5)
        fields1 = [683,853,487,718,372,842,359,778,699,296]
        fields2 = [841,852,682,717,488,423,424,563,562,297,700,777]
        fields3 = [851,848,797,761,721,508,352,355,364,379]
        fields4 = [1866,1834,1835,1804,1734,1655,1565]

        fields = fields1 + fields2
        #fields_complete = fields1 + fields2 # + fields3 + fields4
        #fields = np.arange(300,400)
        #fields = np.arange(700,800)
        #fields = np.setdiff1d(fields,fields_complete)

        #fields = [700]
        #fields = np.arange(250,882)
        #fields = np.arange(750,800)
        #fields = np.arange(250,300)
        #fields = np.arange(600,700)
        #fields = [257]

        for field in fields:
            if opts.doCutNObs:
                if not field in fields_list:
                    continue
            print('Running field %d' % field)
            for ccd in ccds:
                for quadrant in quadrants:
                    if opts.doQuadrantScale:
                        qu = {"query_type":"count_documents",
                              "query": {
                                  "catalog": 'ZTF_sources_20200401',
                                  "filter": {'field': {'$eq': int(field)},
                                             'ccd': {'$eq': int(ccd)},
                                             'quad': {'$eq': int(quadrant)}
                                             }
                                       }
                             }
                        r = ztfperiodic.utils.database_query(kow, qu, nquery = 1)
                        if not "data" in r: continue
                        nlightcurves = r['data']

                        Ncatalog = int(np.ceil(float(nlightcurves)/opts.Nmax))

                        idsFile = os.path.join(idsDir,"%d_%d_%d.npy"%(field, ccd, quadrant))
                        if not os.path.isfile(idsFile):
                            print(idsFile)
                            qu = {"query_type":"find",
                                  "query": {"catalog": 'ZTF_sources_20200401',
                                            "filter": {'field': {'$eq': int(field)},
                                                       'ccd': {'$eq': int(ccd)},
                                                       'quad': {'$eq': int(quadrant)}
                                                      },
                                            "projection": "{'_id': 1}"},
                                 }
                            r = ztfperiodic.utils.database_query(kow, qu, nquery = 10)
                            objids = []
                            for obj in r['data']:
                                objids.append(obj['_id'])
                            np.save(idsFile, objids)

                    for ii in range(Ncatalog):
                        catalogFile = os.path.join(catalogDir,"%d_%d_%d_%d.h5"%(field, ccd, quadrant, ii))
                        if os.path.isfile(catalogFile):
                            print('%s already exists... continuing.' % catalogFile)
                            continue

                        fid1.write('%s %s/ztfperiodic_inject_search.py %s --outputDir %s --program_ids 1,2,3 --field %d --ccd %d --quadrant %d --user %s --pwd %s --batch_size %d -l Kowalski --source_type objid --Ncatalog %d --Ncatindex %d --algorithm %s --doRemoveTerrestrial --doRemoveBrightStars --catalog_file %s --injtype %s %s\n'%(opts.python, dir_path, cpu_gpu_flag, outputDir, field, ccd, quadrant, opts.user, opts.pwd,opts.batch_size, Ncatalog, ii, opts.algorithm, idsFile, injtype, extra_flags))
    
                        fid.write('JOB %d condor.sub\n'%(job_number))
                        fid.write('RETRY %d 3\n'%(job_number))
                        fid.write('VARS %d jobNumber="%d" field="%d" ccd="%d" quadrant="%d" Ncatindex="%d" Ncatalog="%d" idsFile="%s"\n'%(job_number,job_number,field, ccd, quadrant, ii, Ncatalog, idsFile))
                        fid.write('\n\n')
                        job_number = job_number + 1

fid1.close()
fid.close()

fid = open(os.path.join(condorDir,'condor.sub'),'w')
fid.write('executable = %s/ztfperiodic_inject_search.py\n'%dir_path)
fid.write('output = logs/out.$(jobNumber)\n');
fid.write('error = logs/err.$(jobNumber)\n');
fid.write('arguments = %s --outputDir %s --batch_size %d --field $(field) --ccd $(ccd) --quadrant $(quadrant) --Ncatalog $(Ncatalog) --Ncatindex $(Ncatindex) --user %s --pwd %s -l Kowalski --doSaveMemory --doRemoveTerrestrial --doRemoveBrightStars --program_ids 1,2,3 --algorithm %s --catalog_file $(idsFile) --injtype %s %s --source_type objid\n'%(cpu_gpu_flag,outputDir,batch_size,opts.user,opts.pwd,opts.algorithm,injtype,extra_flags))
fid.write('requirements = OpSys == "LINUX"\n');
fid.write('request_memory = 8192\n');
if opts.doCPU:
    fid.write('request_cpus = 1\n');
else:
    fid.write('request_gpus = 1\n');
fid.write('accounting_group = ligo.dev.o2.burst.allsky.stamp\n');
fid.write('notification = never\n');
fid.write('getenv = true\n');
fid.write('log = /local/michael.coughlin/folding.log\n')
fid.write('+MaxHours = 24\n');
fid.write('universe = vanilla\n');
fid.write('queue 1\n');
fid.close()

