"""
*************** DIELECTRIC PROFILE MODULE *******************

Calculates electrostatic properties such as dielectric and
refractive index profiles.

***************************************************************
Created 24/11/2016 by Frank Longford

Contributors: Frank Longford

Last modified 24/11/2016 by Frank Longford
"""
import numpy as np
import scipy as sp
import subprocess, time, sys, os, math, copy
import matplotlib.pyplot as plt

from scipy import stats
from scipy import constants as con
from scipy.optimize import curve_fit, leastsq
import scipy.integrate as spin
from scipy.interpolate import bisplrep, bisplev, splprep, splev

from mpl_toolkits.mplot3d import Axes3D
import matplotlib.cm as cm
from matplotlib.colors import BoundaryNorm
from matplotlib.ticker import MaxNLocator

import utilities as ut


def theta_integrate_y(K, x, DIM, auv, nm, zcom):

	a, b = spin.quad(lambda y: np.sin(np.arccos(np.dot(K, normal_vector(x,y,nm,auv,DIM,zcom))))**2, 0, DIM[1])
	return a

def theta_integrate_x_y(K, DIM, auv, nm, zcom):

	a, b = spin.quad(lambda x: integrate_y(K, x, DIM, auv, nm, zcom), 0, DIM[0])
	return a 

def den_integrate_y(z, x, DIM, auv, nm, zcom):

	a, b = spin.quad(lambda y: int_av_mol_den(z - xi(x, y, nm, zcom)) , 0, DIM[1])
	return a

def den_integrate_x_y(K, DIM, auv, nm, zcom):

	a, b = spin.quad(lambda x: integrate_y(K, x, DIM, auv, nm, zcom), 0, DIM[0])
	return a 


def normal_vector(z, dx, dy, DIM, zcom):

	T = ut.local_frame_surface(dx, dy, z, zcom)
	T = ut.unit_vector(np.sum(T[0]), np.sum(T[1]), np.sum(T[2]))
	
	return T

def dielectric_refractive_index(directory, model, csize, AT, sigma, mol_sigma, nslice, nframe, a_type, DIM):

	atom_types = list(set(AT))
	n_atom_types = len(atom_types)

	Z = np.linspace(0, DIM[2], nslice)
        Z2 = np.linspace(-DIM[2]/2., DIM[2]/2., nslice)

        lslice = DIM[2] / nslice
        ur = 1 #- 9E-6
        angle = 52.9*np.pi/180.
	a = ut.get_polar_constants(model, a_type)

	with file('{}/DEN/{}_{}_{}_DEN.npy'.format(directory, model.lower(), nslice, nframe), 'r') as infile:
                av_density = np.load(infile)

	mol_den = av_density[-1]

	if model.upper() == 'ARGON':
		axx = np.ones(nslice) * a
		azz = np.ones(nslice) * a
	else:
		with file('{}/EULER/{}_{}_{}_{}_EUL.npy'.format(directory, model.lower(), a_type, nslice, nframe), 'r') as infile:
			axx, azz, _, _, _, _, _ = np.load(infile)

	exx = np.array([(1 + 8 * np.pi / 3. * mol_den[n] * axx[n]) / (1 - 4 * np.pi / 3. * mol_den[n] * axx[n]) for n in range(nslice)])
        ezz = np.array([(1 + 8 * np.pi / 3. * mol_den[n] * azz[n]) / (1 - 4 * np.pi / 3. * mol_den[n] * azz[n]) for n in range(nslice)])

        no = np.sqrt(ur * exx)
        ni = np.sqrt(ur * ezz)

	popt, pcov = curve_fit(ut.den_func, Z, exx, [1., 1., DIM[2]/2., DIM[2]/4., 2.])
        param = np.absolute(popt)
        sm_exx = map (lambda x: ut.den_func(x, param[0], 1, param[2], param[3], param[4]), Z)

        popt, pcov = curve_fit(ut.den_func, Z, ezz, [1., 1., DIM[2]/2., DIM[2]/4., 2.])
        param = np.absolute(popt)
        sm_ezz = map (lambda x: ut.den_func(x, param[0], 1, param[2], param[3], param[4]), Z)

	popt, pcov = curve_fit(ut.den_func, Z, no, [1., 1., DIM[2]/2., DIM[2]/4., 2.])
        param = np.absolute(popt)
        no_sm = map (lambda x: ut.den_func(x, param[0], 1, param[2], param[3], param[4]), Z)

	popt, pcov = curve_fit(ut.den_func, Z, ni, [1., 1., DIM[2]/2., DIM[2]/4., 2.])
        param = np.absolute(popt)
	ni_sm = map (lambda x: ut.den_func(x, param[0], 1, param[2], param[3], param[4]), Z)

	with file('{}/DIELEC/{}_{}_{}_{}_DIE.npy'.format(directory, model.lower(), a_type, nslice, nframe), 'w') as outfile:
		np.save(outfile, (exx, ezz))
	with file('{}/DIELEC/{}_{}_{}_{}_DIE_SM.npy'.format(directory, model.lower(), a_type, nslice, nframe), 'w') as outfile:
                np.save(outfile, (sm_exx, sm_ezz))
	with file('{}/DIELEC/{}_{}_{}_{}_ELLIP_NO.npy'.format(directory, model.lower(), a_type, nslice, nframe), 'w') as outfile:
                np.save(outfile, (no, ni))
	with file('{}/DIELEC/{}_{}_{}_{}_ELLIP_NO_SM.npy'.format(directory, model.lower(), a_type, nslice, nframe), 'w') as outfile:
		np.save(outfile, (no_sm, ni_sm))

	print "{} {} {} COMPLETE\n".format(directory, model.upper(), csize)


