#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Jan van Roestel and Michael Coughlin

06/2020
"""

import numpy as np
import copy
from scipy.stats import anderson, shapiro
import scipy.optimize
from scipy.optimize import curve_fit


def calc_weighted_mean_std(mag,w):
    """ Calculate the weighted mean and std values

    Parameters
    ----------
    a : 1D-array
        array with values
    weights : 1D-array
        array with weights

    Returns
    -------
    results : list

        array of statistics

    """
    average = np.average(mag, weights=w)
    variance = np.average((mag-average)**2, weights=w)
    return average,np.sqrt(variance)  



def calc_smallkurt(mag,err,N,mean):
    """ calculate small kurt
    """
    smallkurt = 1.*N*(N+1)/(N-1)/(N-2)/(N-3) 
    smallkurt *= np.sum(((mag-mean)/err)**4)
    smallkurt -= 3*(N-1)**2/(N-2)/(N-3)
    return smallkurt



def calc_Stetson(mag,err,N,wmean):
    """Calculate the Welch/Stetson I and Stetson J,K statistics
    e.g. https://www.aanda.org/articles/aa/pdf/2016/02/aa26733-15.pdf"""
    d = np.sqrt(1.*N/(N-1))*(mag-wmean)/err
    P = d[:-1]*d[1:]

    # stetsonI
    I = np.sum(P)

    # stetsonJ
    J = np.sum(np.sign(P)*np.sqrt(np.abs(P)))

    # stetsonJ time
    

    # stetsonK
    K = np.sum(abs(d))/N
    K /= np.sqrt(1./N*np.sum(d**2))

    return I,J,K



def calc_invNeumann(t,mag,wstd):
    """Calculate the time-weighted inverse Von Neumann stat
    """
    dt = t[1:] - t[:-1]
    dm = mag[1:] - mag[:-1]

    w = (dt)**-2 # inverse deltat weighted
    eta = np.sum(w*dm**2)
    eta /= np.sum(w)*wstd**2

    return eta**-1



def calc_NormExcessVar(mag,err,N,wmean):
    stat = np.sum((mag-wmean)**2-err**2)
    stat /= N*wmean**2
    return stat



def calc_NormPeaktoPeakamp(mag,err):
    stat = np.max(mag-err) - np.min(mag+err)
    stat /= np.max(mag-err) + np.min(mag+err)
    return stat



def fourier_decomposition(t,y,dy,p,maxNterms=5,relative_output=True):

    N = np.size(y)

    f = make_f(p=p)
    chi2 = np.zeros(maxNterms+1,dtype=float) # fill in later
    pars = np.zeros((maxNterms+2,(maxNterms+1)*2)) # fill in later

    
    init = np.array([np.median(y),0.000001]) # the initial values for the minimiser
    #print(t,y,dy,init)
    for i,Nterms in enumerate(np.arange(maxNterms+1.,dtype=int)):
        popt, pcov = curve_fit(make_f(p), # function
            t, y, # t,dy
            init, # initial values [1.0]*2
            sigma=dy # dy
            )

        init = np.r_[init,0.1*np.ones(2)]

        pars[i,:2*(i+1)] = popt
        # make the model
        model = f(t, *popt)
        chi2[i] = np.sum(((y-model)/dy)**2)

    # calc BICs
    BIC = chi2 + np.log(N)* (2+2*np.arange(maxNterms+1,dtype=float))
    best = np.argmin(BIC)
    
    power = (chi2[0]-chi2[best])/chi2[0]
    bestBIC = BIC[best]
    bestpars = pars[best,:]

    if relative_output:
        bestpars[2:] = AB2AmpPhi(bestpars[2:])

    return np.r_[power,bestBIC,bestpars]



def AB2AmpPhi(input_arr):
    """ convert an array of fourier components (A,B) to amp,phase and normalise

    input:
        arr : array of fourier components, A&B
    
    output:
        arr : array of fourier amplitudes and phases. The phase differences are 
                normalised between 0 and 1.
    """

    arr = copy.deepcopy(input_arr)

    # convert A,B to amp and phi
    for n in np.arange(0,np.size(arr),2):
        amp = np.sqrt(arr[n]**2 + arr[n+1]**2)
        phi = np.arctan2(arr[n],arr[n+1])
        arr[n] = amp
        arr[n+1] = phi

    # normalise
    arr[2::2] /= arr[0] # normalise amplitudes

    # report phase shift

    maxk = int(np.size(input_arr)/2)
    for k in range(2,maxk+1,1):
        arr[k*2-1] = (arr[k*2-1]/k-arr[1])/(2.*np.pi/k)%1

    return arr



def make_f(p):
    """ Function that returns a fourier function for period p
    input 
        p: period

    output:
        f: function
    
    """
    def f(t, *pars):
        """A function which returns a fourier model, inluding offset and slope
        input:
            t: array with times
            pars: list of parameters: [offset, slope, a_1,b_1,a_2,b_2,...]    
    
        """

        #print(pars)

        #pars = np.array(pars)
        # a offset a[0], and slope
        y = pars[0] + pars[1] * (t-np.min(t))
        # fourier components, loops from 1 to ?
        for n in np.arange(1,(len(pars)-2)/2+1,1,dtype=int):
            phi = 2*np.pi*t/p
            y += pars[n*2] * np.cos(n * phi)
            y += pars[n*2+1] * np.sin(n * phi)
        return y
    return f



def calc_basic_stats(t,mag,err):

    N = np.size(mag)

    # basic stats
    median = np.median(mag)
    w = err**-2
    wmean, wstd = calc_weighted_mean_std(mag,w)
    chi2red = np.sum((wmean-mag)**2*w)/(N-1)
    RoMS = np.sum(abs(mag-median)/err)/(N-1)

    # deviation from median
    NormPeaktoPeakamp = calc_NormPeaktoPeakamp(mag,err)
    NormExcessVar = calc_NormExcessVar(mag,err,N,wmean)
    medianAbsDev = np.median(abs(mag-median))
    iqr = np.diff(np.percentile(mag,q=[25,75]))[0]
    i60r = np.diff(np.percentile(mag,q=[20,80]))[0]
    i70r = np.diff(np.percentile(mag,q=[15,85]))[0]
    i80r = np.diff(np.percentile(mag,q=[10,90]))[0]
    i90r = np.diff(np.percentile(mag,q=[5,95]))[0]

    # other variability stats
    skew = 1.*N/(N-1)/(N-2) * np.sum(((mag-wmean)/err)**3)
    smallkurt = calc_smallkurt(mag,err,N,wmean)
    invNeumann = calc_invNeumann(t,mag,wstd)
    WelchI,StetsonJ,StetsonK = calc_Stetson(mag,err,N,wmean)
    AD = anderson(mag/err)[0]
    SW = shapiro(mag/err)[0]

    return np.r_[N,median,wmean,chi2red,RoMS,wstd,
                NormPeaktoPeakamp,NormExcessVar,medianAbsDev,iqr,
                i60r,i70r,i80r,i90r,skew,smallkurt,invNeumann,
                WelchI,StetsonJ,StetsonK,AD,SW]




def calc_stats(t,mag,err,p):

    # calculate basic stats
    (N,median,wmean,chi2red,Roms,wstd,
    NormPeaktoPeakamp,NormExcessVar,medianAbsDev,iqr,
    F60,F70,F80,F90,skew,smallkurt,invNeumann,
    WelchI,StetsonJ,StetsonK,AD,SW) = calc_basic_stats(t,mag,err)

    try:
        # fourier decomposition stuff
        (f1_power,f1_BIC,f1_a,f1_b,f1_amp,f1_phi0,
            f1_relamp1,f1_relphi1,f1_relamp2,f1_relphi2,
            f1_relamp3,f1_relphi3,f1_relamp4,f1_relphi5
            ) = fourier_decomposition(t,mag,err,p)
    except:
        (f1_power,f1_BIC,f1_a,f1_b,f1_amp,f1_phi0,
        f1_relamp1,f1_relphi1,f1_relamp2,f1_relphi2,
        f1_relamp3,f1_relphi3,f1_relamp4,f1_relphi5) = \
        (np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
        np.nan, np.nan, np.nan, np.nan,
        np.nan, np.nan, np.nan, np.nan)

    # return all
    return np.r_[N,median,wmean,chi2red,Roms,wstd,
                 NormPeaktoPeakamp,NormExcessVar,medianAbsDev,iqr,
                 F60,F70,F80,F90,skew,smallkurt,invNeumann,
                 WelchI,StetsonJ,StetsonK,AD,SW,
                 f1_power,f1_BIC,f1_a,f1_b,f1_amp,f1_phi0,
                 f1_relamp1,f1_relphi1,f1_relamp2,f1_relphi2,
                 f1_relamp3,f1_relphi3,f1_relamp4,f1_relphi5]


def calc_fourier_stats(t,mag,err,p):

    try:
        # fourier decomposition stuff
        (f1_power,f1_BIC,f1_a,f1_b,f1_amp,f1_phi0,
            f1_relamp1,f1_relphi1,f1_relamp2,f1_relphi2,
            f1_relamp3,f1_relphi3,f1_relamp4,f1_relphi5
            ) = fourier_decomposition(t,mag,err,p)
    except:
        (f1_power,f1_BIC,f1_a,f1_b,f1_amp,f1_phi0,
        f1_relamp1,f1_relphi1,f1_relamp2,f1_relphi2,
        f1_relamp3,f1_relphi3,f1_relamp4,f1_relphi5) = \
        (np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
        np.nan, np.nan, np.nan, np.nan,
        np.nan, np.nan, np.nan, np.nan)

    # return all
    return np.r_[f1_power,f1_BIC,f1_a,f1_b,f1_amp,f1_phi0,
                 f1_relamp1,f1_relphi1,f1_relamp2,f1_relphi2,
                 f1_relamp3,f1_relphi3,f1_relamp4,f1_relphi5] 
