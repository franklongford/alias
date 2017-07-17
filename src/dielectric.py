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
import intrinsic_surface as IS


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

def surface_ne(root, model, csize, nm, nxy, int_exx, int_ezz, DIM, nimage, thetai):

	nslice = len(int_exx)
	X = np.linspace(0, DIM[0], nxy)
	Y = np.linspace(0, DIM[1], nxy)
	Z = np.linspace(-DIM[2]/2, DIM[2]/2, nslice)

	angle1 = np.zeros((nimage,nxy,nxy))
	angle2 = np.zeros((nimage,nxy,nxy))

	K = ut.unit_vector(0 , np.cos(thetai), np.sin(thetai))
	unit = np.sqrt(1/2.)
	print K, np.arccos(np.dot(K, ([0,1,0]))) * 180 / np.pi, thetai * 180 / np.pi

	T_int_anis = np.zeros(nslice)

	print 'PROCESSING SURFACE CURVATURE'
	for i in xrange(nimage):
		sys.stdout.write("CALCULATING {} out of {} ANGLES\r".format(i+1, nimage) )
		sys.stdout.flush()
		
		with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_{}_CURVE.npz'.format(root, model.lower(), csize, nslice, nm, nxy, i), 'r') as infile:
			npzfile = np.load(infile)
			XI1 = npzfile['XI1']
			XI2 = npzfile['XI2']
			DX1 = npzfile['DX1']
			DY1 = npzfile['DY1']
			DX2 = npzfile['DX2']
			DY2 = npzfile['DY2']
		for j in xrange(nxy):
			x = X[j]
			for k in xrange(nxy):
				y = Y[k]
				angle1[i][j][k] = np.arccos(np.dot(K, normal_vector(Eta1[j][k], Dx1[j][k], Dy1[j][k], DIM,)))
				angle2[i][j][k] = np.arccos(np.dot(K, normal_vector(Eta2[j][k], Dx2[j][k], Dy2[j][k], DIM)))

	print "\n"

	for i in xrange(nimage):
		sys.stdout.write("READJUSTING {} out of {} ORIENTATIONS\r".format(i+1, nimage) )
		sys.stdout.flush()
		"""
		if os.path.exists('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_ANIS.txt'.format(root, model.lower(), csize, nslice, nm, nxy, i)): A = 1
			with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_ANIS.txt'.format(root, model.lower(), csize, nslice, nm, nxy, i)) as infile:
				T_int_anis += np.loadtxt(infile) / nimage

		else:
		"""

		plane1 = 0
		plane2 = 0

		for j in xrange(nxy):
			x = X[j]
			for k in xrange(nxy):
				y = Y[k]
				plane1 += np.sin(angle1[i][j][k])**2  / (nxy**2)
				plane2 += np.sin(angle2[i][j][k])**2  / (nxy**2)

		print plane1 * 180 / np.pi, plane2 * 180 / np.pi

		int_anis = np.zeros(nslice)

		for n in xrange(nslice):
			prefac = (int_ezz[n] - int_exx[n]) / int_ezz[n]
			if Z[n] < 0: int_anis[n] += (1 - prefac * plane1) 
			else: int_anis[n] += (1 - prefac * plane2)

		int_anis2 = np.zeros(nslice)

		for n in xrange(nslice):
			prefac = (int_ezz[n] - int_exx[n]) / int_ezz[n]
			for j in xrange(nxy):
				x = X[j]
				for k in xrange(nxy):
					y = Y[k]
					if Z[n] < 0: int_anis2[n] += (1 - prefac * np.sin(angle1[i][j][k])**2) / (nxy**2)
					else: int_anis2[n] += (1 - prefac * np.sin(angle2[i][j][k])**2) / (nxy**2)

		print np.sum(int_anis - int_anis2)
		T_int_anis += int_anis / nimage
		with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_ANIS.txt'.format(root, model.lower(), csize, nslice, nm, nxy, i), 'w') as outfile:
			np.savetxt(outfile, (int_anis), fmt='%-12.6f')
	print "\n"

	return T_int_anis


def dielectric_refractive_index(directory, model, csize, AT, sigma, nslice, nimage, a_type, nm, DIM, ow_ecount, ow_acount):

	atom_types = list(set(AT))
	n_atom_types = len(atom_types)

	mean_auv1 = np.zeros(nimage)
	mean_auv2 = np.zeros(nimage)

	av_auv1_2 = np.zeros((2*nm+1)**2)
	av_auv2_2 = np.zeros((2*nm+1)**2)

	print "PROCESSING DIELECTRIC AND REFRACTIVE INDEX PROFILES\n"

	if model.upper() == 'ARGON':
		if a_type == 'exp': argon_exp_a = 1.642

		axx = np.ones(nslice) * argon_exp_a 
		azz = np.ones(nslice) * argon_exp_a 
		int_axx = np.ones(nslice) * argon_exp_a 
		int_azz = np.ones(nslice) * argon_exp_a
		int_axx1 = np.ones(nslice) * argon_exp_a 
		int_azz1 = np.ones(nslice) * argon_exp_a
		int_axx2 = np.ones(nslice) * argon_exp_a 
		int_azz2 = np.ones(nslice) * argon_exp_a 

	else:
		with file('{}/DATA/EULER/{}_{}_{}_{}_{}_EUL.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage), 'r') as infile:
			axx, azz, _, _, _, _, _ = np.loadtxt(infile)
		with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_{}_EUL1.txt'.format(directory, model.lower(), csize, nslice, a_type, nm, nimage), 'r') as infile:
			int_axx1, int_azz1,  _, _, _, _, _ = np.loadtxt(infile)
		with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_{}_EUL2.txt'.format(directory, model.lower(), csize, nslice, a_type, nm, nimage), 'r') as infile:
			int_axx2, int_azz2,  _, _, _, _, _ = np.loadtxt(infile)

	with file('{}/DATA/DEN/{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, nimage), 'r') as infile:
		av_density = np.loadtxt(infile)
	with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, nm, nimage), 'r') as infile:
		av_int_density = np.loadtxt(infile)

	Z = np.linspace(0, DIM[2], nslice)
	Z2 = np.linspace(-DIM[2]/2., DIM[2]/2., nslice)

	lslice = DIM[2] / nslice
	ur = 1 #- 9E-6
	angle = 52.9*np.pi/180.
	mol_den = av_density[-1]
	mol_int_den = 0.5 * (av_int_density[-4] + av_int_density[-3][::-1])

	exx = np.array([(1 + 8 * np.pi / 3. * mol_den[n] * axx[n]) / (1 - 4 * np.pi / 3. * mol_den[n] * axx[n]) for n in range(nslice)])
	ezz = np.array([(1 + 8 * np.pi / 3. * mol_den[n] * azz[n]) / (1 - 4 * np.pi / 3. * mol_den[n] * azz[n]) for n in range(nslice)])

	no = np.sqrt(ur * exx)
	ni = np.sqrt(ur * ezz)
	#anis = np.array([1 - (ezz[n] - exx[n]) * np.sin(angle)**2 / ezz[n] for n in range(nslice)])
	#ne = np.array([np.sqrt(ur * exx[n] / anis[n]) for n in range(nslice)])
	
	popt, pcov = curve_fit(ut.den_func, Z, no, [1., 1., DIM[2]/2., DIM[2]/4., 2.])
	param = np.absolute(popt)
	no_sm = map (lambda x: ut.den_func(x, param[0], 1, param[2], param[3], param[4]), Z)

	int_axx = 0.5 * (int_axx1 + int_axx2[::-1])
	int_azz = 0.5 * (int_azz1 + int_azz2[::-1])

	rho_axx =  np.array([mol_int_den[n] * int_axx[n] for n in range(nslice)])
	rho_azz =  np.array([mol_int_den[n] * int_azz[n] for n in range(nslice)])

	int_exx = np.array([(1 + 8 * np.pi / 3. * rho_axx[n]) / (1 - 4 * np.pi / 3. * rho_axx[n]) for n in range(nslice)])
	int_ezz = np.array([(1 + 8 * np.pi / 3. * rho_azz[n]) / (1 - 4 * np.pi / 3. * rho_azz[n]) for n in range(nslice)])

	int_no = np.sqrt(ur * int_exx)
	int_ni = np.sqrt(ur * int_ezz)
	#anis = np.array([1 - (av_int_ezz[n] - av_int_exx[n]) * np.sin(angle)**2 / av_int_ezz[n] for n in range(nslice)])
	#int_ne = np.array([np.sqrt(ur * av_int_exx[n] / anis[n]) for n in range(nslice)])

	print "BUILDING CAPILLARY WAVE DIELECTRIC PROFILE"
	for image in xrange(nimage):
		sys.stdout.write("LOADING SURFACE VARIANCE {} out of {} images\r".format(image, nimage))
                sys.stdout.flush()

		with file('{}/DATA/ACOEFF/{}_{}_{}_{}_INTCOEFF.txt'.format(directory, model.lower(), csize, nm, image), 'r') as infile: 
			auv1, auv2 = np.loadtxt(infile)

		av_auv1_2 += auv1**2 / nimage
		av_auv2_2 += auv2**2 / nimage

		mean_auv1[image] += auv1[len(auv1)/2]
                mean_auv2[image] += auv2[len(auv2)/2]

	Delta1 = (ut.sum_auv_2(av_auv1_2, nm) - np.mean(mean_auv1)**2)
	Delta2 = (ut.sum_auv_2(av_auv2_2, nm) - np.mean(mean_auv2)**2)

	print "GAUSSIAN WIDTHS: {} {}  AVERAGE = {}".format(Delta1, Delta2, 0.5*(Delta1+Delta2))

	centres = np.ones(9) * np.mean(mean_auv1)
	deltas = np.ones(9) * 0.5 * (Delta1 + Delta2)

	cw_arrays = ut.gaussian_smoothing((mol_int_den, int_axx, int_azz, rho_axx, rho_azz, int_exx, int_ezz, int_no, int_ni), centres, deltas, DIM, nslice)

	cw_exx1 = np.array([(1 + 8 * np.pi / 3. * cw_arrays[0][n] * cw_arrays[1][n]) / (1 - 4 * np.pi / 3. * cw_arrays[0][n] * cw_arrays[1][n]) for n in range(nslice)])
	cw_ezz1 = np.array([(1 + 8 * np.pi / 3. * cw_arrays[0][n] * cw_arrays[2][n]) / (1 - 4 * np.pi / 3. * cw_arrays[0][n] * cw_arrays[2][n]) for n in range(nslice)])

	cw_exx2 = np.array([(1 + 8 * np.pi / 3. * cw_arrays[3][n]) / (1 - 4 * np.pi / 3. * cw_arrays[3][n]) for n in range(nslice)])
	cw_ezz2 = np.array([(1 + 8 * np.pi / 3. * cw_arrays[4][n]) / (1 - 4 * np.pi / 3. * cw_arrays[4][n]) for n in range(nslice)])

	"""
	cw_int_no1 = np.sqrt(ur * cw_int_exx1)
	anis = np.array([1 - (cw_int_ezz1[n] - cw_int_exx1[n]) * np.sin(angle)**2 / cw_int_ezz1[n] for n in range(nslice)])
	cw_int_ne1 = np.array([np.sqrt(ur * cw_int_exx1[n] / anis[n]) for n in range(nslice)])
	cw_int_ni1 = np.sqrt(ur * cw_int_ezz1)

	cw_int_no2 = np.sqrt(ur * cw_int_exx2)
	anis = np.array([1 - (cw_int_ezz2[n] - cw_int_exx2[n]) * np.sin(angle)**2 / cw_int_ezz2[n] for n in range(nslice)])
	cw_int_ne2 = np.array([np.sqrt(ur * cw_int_exx2[n] / anis[n]) for n in range(nslice)])
	cw_int_ni2 = np.sqrt(ur * cw_int_ezz2)
	"""

	plt.plot(int_exx)
	plt.plot(int_ezz)
	plt.plot(cw_arrays[5])
	plt.plot(cw_arrays[6])
	plt.show()

	print "WRITING TO FILE..."

	with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_DIE.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage), 'w') as outfile:
		np.savetxt(outfile, (exx, ezz), fmt='%-12.6f')
	with file('{}/DATA/INTDIELEC/{}_{}_{}_{}_{}_{}_DIE.txt'.format(directory, model.lower(), csize, nslice, a_type, nm, nimage), 'w') as outfile:
		np.savetxt(outfile, (int_exx, int_ezz), fmt='%-12.6f')
	with file('{}/DATA/INTDIELEC/{}_{}_{}_{}_{}_{}_CWDIE.txt'.format(directory, model.lower(), csize, nslice, a_type, nm, nimage), 'w') as outfile:
		np.savetxt(outfile, (cw_exx1, cw_ezz1, cw_exx2, cw_ezz2, cw_arrays[5], cw_arrays[6]), fmt='%-12.6f')
	with file('{}/DATA/ELLIP/{}_{}_{}_{}_{}_{}_ELLIP_NO.txt'.format(directory, model.lower(), csize, nslice, a_type, nm, nimage), 'w') as outfile:
		np.savetxt(outfile, (no_sm, np.sqrt(cw_exx1), np.sqrt(cw_exx2), np.sqrt(cw_arrays[5]), cw_arrays[7]), fmt='%-12.6f')

	print "{} {} {} COMPLETE\n".format(directory, model.upper(), csize)


def main(root, model, nsite, AT, Q, M, LJ, T, cutoff, csize, TYPE, folder, sfolder, nfolder, suffix, nimage=0):

	#a_type = raw_input("Polarisability Parameter type? (exp, ame, abi)?: ")	
	if model.upper() in ['METHANOL', 'ETHANOL', 'DMSO']: a_type = 'calc'
	else: a_type = 'exp'

	for i in xrange(sfolder, nfolder):
		if TYPE.upper() != 'SLAB': directory = '{}/{}_{}'.format(root, TYPE.upper(), i)
		else: directory = root	
		traj = ut.load_nc(directory, folder, model, csize, suffix)						
		directory = '{}/{}'.format(directory, folder.upper())

		natom = traj.n_atoms
		nmol = traj.n_residues
		if nimage == 0: ntraj = traj.n_frames
		else: ntraj = nimage
		DIM = np.array(traj.unitcell_lengths[0]) * 10
		sigma = np.max(LJ[1])
		lslice = 0.05 * sigma
		nslice = int(DIM[2] / lslice)
		vlim = 3
		ncube = 3
		nm = int((DIM[0] + DIM[1]) / (2 * sigma))
		nxy = int((DIM[0]+DIM[1])/ sigma)

		if not os.path.exists("{}/DATA/DIELEC".format(directory)): os.mkdir("{}/DATA/DIELEC".format(directory))
		if os.path.exists('{}/DATA/DIELEC/{}_{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage)):
			print '\nFILE FOUND {}/DATA/DIELEC/{}_{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage)
			overwrite = raw_input("OVERWRITE? (Y/N): ")
			if overwrite.upper() == 'Y':  
				ow_E = raw_input("OVERWRITE ECOUNT? (Y/N): ") 
				dielectric_refractive_index(directory, model, csize, AT, sigma, nslice, nimage, a_type, nm, nxy, DIM, ow_E)
		else: dielectric_refractive_index(directory, model, csize, AT, sigma, nslice, nimage, a_type, nm, nxy, DIM, 'Y')



