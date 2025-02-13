#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 31 15:05:27 2017

@author: kburdge
"""

import os
import optparse
import numpy as np
import h5py
import glob
import pickle
import json

import matplotlib
matplotlib.use('Agg')
fs = 24
font = {'family' : 'normal',
        'weight' : 'normal',
        'size'   : fs}
matplotlib.rc('font', **font)
matplotlib.rcParams['contour.negative_linestyle'] = 'solid'
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from astropy.table import Table

def parse_commandline():
    """
    Parse the options given on the command-line.
    """
    parser = optparse.OptionParser()

    parser.add_option("-o", "--outputDir", default="../output/forced")
    parser.add_option("--datafile", default="/Users/mcoughlin/Downloads/lc_friends_raw.txt")
   
    parser.add_option("--doPhase", action="store_true", default=False)
    parser.add_option("-p", "--phase", default=0.16776, type=float)
 
    opts, args = parser.parse_args()

    return opts

# Parse command line
opts = parse_commandline()
datafile = opts.datafile
outputDir = opts.outputDir
phase = opts.phase

if not os.path.isdir(outputDir):
    os.makedirs(outputDir)

data = Table.read(datafile, format='ascii', data_start=1)

hjd, flux, fluxerr, fids = [], [], [], []
for a, b, c, d in zip(data["col23"], data["col25"], data["col26"], data["col5"]):
    if b == "null": continue
    hjd.append(a)
    flux.append(float(b))
    fluxerr.append(float(c))
    fids.append(d.split("_")[1])

hjd, flux, fluxerr, fids = np.array(hjd), np.array(flux), np.array(fluxerr), np.array(fids)

hjd_mod = np.mod(hjd,2*phase)/(2*phase)
idx = np.argsort(hjd_mod)
hjd_mod = hjd_mod[idx]
flux_mod = flux[idx]
fluxerr_mod = fluxerr[idx]
fids_mod = fids[idx]        

colors = ['g','r','y']
symbols = ['x', 'o', '^']
fids = [1,2,3]
bands = ['g', 'r', 'i']

plotName = os.path.join(outputDir,'phase.pdf')
plt.figure(figsize=(7,5))
for band, color, symbol in zip(bands, colors, symbols):
    idx = np.where(band == fids_mod)[0]
    print(idx)
    plt.errorbar(hjd_mod[idx],flux_mod[idx],yerr=fluxerr_mod[idx],fmt='%s%s' % (color, symbol), label=band)
plt.xlabel('Phase')
plt.ylabel('Flux')
plt.legend()
plt.tight_layout()
plt.savefig(plotName)
plt.close()
