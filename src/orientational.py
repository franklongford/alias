"""
*************** ORIENTATIONAL ANALYSIS MODULE *******************

Calculates Euler angle profile and polarisability of system

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


def R_tensors(directory, image, nslice, nmol, model, csize, COM, DIM, nsite, nm):

	temp_O = np.zeros((nslice, 9))
	temp_int_O1 = np.zeros((nslice, 9))
	temp_int_O2 = np.zeros((nslice, 9))

	with file('{}/DATA/INTPOS/{}_{}_{}_{}_INTZ_MOL.txt'.format(directory, model.lower(), csize, nm, image), 'r') as infile:
		int_z_mol_1, int_z_mol_2 = np.loadtxt(infile)

	xat, yat, zat = ut.read_atom_positions(directory, model, csize, image)
	xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, image)
	xR, yR, zR = COM[image]

	for j in xrange(nmol):
		sys.stdout.write("PROCESSING {} ODIST {}: {} out of {}  molecules\r".format(directory, image, j, nmol))
		sys.stdout.flush()

		MOLECULE = np.zeros((nsite, 3))

		for l in xrange(nsite):
			MOLECULE[l][0] = xat[j*nsite+l]
			MOLECULE[l][1] = yat[j*nsite+l]
			MOLECULE[l][2] = zat[j*nsite+l]

		z = zmol[j] - zR
		zeta1 = zmol[j] - zR - int_z_mol_1[j] 
		zeta2 = - zmol[j] + zR + int_z_mol_2[j]

		"""NORMAL Z AXIS"""

		O = ut.local_frame_molecule(MOLECULE, model)
		if O[2][2] < -1: O[2][2] = -1.0
		elif O[2][2] > 1: O[2][2] = 1.0

		""" INTRINSIC SURFACE DERIVATIVE """
		"""
		T = ut.local_frame_surface(dzx1, dzy1, -1)
		R1 = np.dot(O, np.linalg.inv(T))
		if R1[2][2] < -1: R1[2][2] = -1.0
		elif R1[2][2] > 1: R1[2][2] = 1.0

		T = ut.local_frame_surface(dzx2, dzy2, 1)
		R2 = np.dot(O, np.linalg.inv(T))
		if R2[2][2] < -1: R2[2][2] = -1.0
		elif R2[2][2] > 1: R2[2][2] = 1.0
		"""

		index1 = int((z + DIM[2]/2) * nslice / DIM[2]) % nslice
		int_index11 = int((zeta1 + DIM[2]/2) * nslice / DIM[2]) % nslice
		int_index12 = int((zeta2 + DIM[2]/2) * nslice / DIM[2]) % nslice

		for k in xrange(3):
			for l in xrange(3):
				index2 = k * 3 + l 
				temp_O[index1][index2] += O[k][l]**2
				temp_int_O1[int_index11][index2] += O[k][l]**2
				temp_int_O2[int_index12][index2] += O[k][l]**2
		
	with file('{}/DATA/EULER/{}_{}_{}_{}_ODIST.txt'.format(directory, model.lower(), csize, nslice, image), 'w') as outfile:
		np.savetxt(outfile, temp_O, fmt='%-12.6f')
	with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_ODIST1.txt'.format(directory, model.lower(), csize, nslice, nm, image), 'w') as outfile:
		np.savetxt(outfile, temp_int_O1, fmt='%-12.6f')
	with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_ODIST2.txt'.format(directory, model.lower(), csize, nslice, nm, image), 'w') as outfile:
		np.savetxt(outfile, temp_int_O2, fmt='%-12.6f')

	return temp_O, temp_int_O1, temp_int_O2


def mol_angles(directory, image, nslice, nmol, model, csize, COM, DIM, nsite, nm):

	z_array = np.zeros(nmol)
	theta = np.zeros(nmol)
	phi = np.zeros(nmol)
	varphi = np.zeros(nmol)

	zeta_array1 = np.zeros(nmol)
	int_theta1 = np.zeros(nmol)
	int_phi1 = np.zeros(nmol)
	int_varphi1 = np.zeros(nmol)

	zeta_array2 = np.zeros(nmol)
	int_theta2 = np.zeros(nmol)
	int_phi2 = np.zeros(nmol)
	int_varphi2 =np.zeros(nmol)

	with file('{}/DATA/INTPOS/{}_{}_{}_{}_INTZ_MOL.txt'.format(directory, model.lower(), csize, nm, image), 'r') as infile:
		int_z_mol_1, int_z_mol_2 = np.loadtxt(infile)

	if os.path.exists('{}/DATA/INTPOS/{}_{}_{}_{}_INTDXDY_MOL.txt'.format(directory, model.lower(), csize, nm, image)):
		with file('{}/DATA/INTPOS/{}_{}_{}_{}_INTDXDY_MOL.txt'.format(directory, model.lower(), csize, nm, image), 'r') as infile:
			dxdyz_mol = np.loadtxt(infile)
		make_dxdy = False
	else:			
		with file('{}/DATA/ACOEFF/{}_{}_{}_{}_INTCOEFF.txt'.format(directory, model.lower(), csize, nm, image), 'r') as infile:
                        auv1, auv2 = np.loadtxt(infile)

		dxdyz_mol = [np.zeros(nmol) for n in range(4)]
		make_dxdy = True

	xat, yat, zat = ut.read_atom_positions(directory, model, csize, image)
	xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, image)
	xR, yR, zR = COM[image]

	for j in xrange(nmol):
		sys.stdout.write("PROCESSING {} ANGLES {}: make_dxdy = {}  {} out of {}  molecules\r".format(directory, image, make_dxdy, j, nmol) )
		sys.stdout.flush()

		MOLECULE = np.zeros((nsite, 3))

		for l in xrange(nsite):
			MOLECULE[l][0] = xat[j*nsite+l]
			MOLECULE[l][1] = yat[j*nsite+l]
			MOLECULE[l][2] = zat[j*nsite+l]

		z = zmol[j] - zR
		zeta1 = zmol[j] - zR - int_z_mol_1[j] 
		zeta2 = - zmol[j] + zR + int_z_mol_2[j]

		if make_dxdy:
			dzx1, dzy1 = IS.dxyi(xmol[j], ymol[j], nm, auv1, DIM)			
			dzx2, dzy2 = IS.dxyi(xmol[j], ymol[j], nm, auv2, DIM)
		
			dxdyz_mol[0][j] = dzx1
			dxdyz_mol[1][j] = dzy1
			dxdyz_mol[2][j] = dzx2
			dxdyz_mol[3][j] = dzy2
		else:
			dzx1 = dxdyz_mol[0][j]
			dzy1 = dxdyz_mol[1][j]
			dzx2 = dxdyz_mol[2][j]
			dzy2 = dxdyz_mol[3][j]

		"""NORMAL Z AXIS"""

		O = ut.local_frame_molecule(MOLECULE, model)

		z_array[j] = z
		if O[2][2] < -1: O[2][2] = -1.0
		elif O[2][2] > 1: O[2][2] = 1.0
		theta[j] = np.arccos(O[2][2])			
		phi[j] = (np.arctan(-O[2][0] / O[2][1]))
		varphi[j] =  (np.arctan(O[0][2] / O[1][2]))

		#print "\n{} {} {}".format(np.arccos(O[2][2]), np.arctan(-O[2][0]/O[2][1]), np.arctan(O[0][2]/O[1][2]))
		
		""" INTRINSIC SURFACE """
		"""
		zeta_array1[image][j] = zeta1
		int_theta1[image][j] = np.arccos(O[2][2])
		int_phi1[image][j] = np.arctan2(-O[2][0],O[2][1])
		int_varphi1[image][j] = np.arctan2(O[0][2],O[1][2])

		zeta_array2[image][j] = zeta2
		int_theta2[image][j] = np.arccos(O[2][2])
		int_phi2[image][j] = np.arctan2(-O[2][0],O[2][1])
		int_varphi2[image][j] = np.arctan2(O[0][2],O[1][2])
		"""
		""" INTRINSIC SURFACE DERIVATIVE """

		T = ut.local_frame_surface(dzx1, dzy1, -1)
		R1 = np.dot(O, np.linalg.inv(T))
		if R1[2][2] < -1: R1[2][2] = -1.0
		elif R1[2][2] > 1: R1[2][2] = 1.0
		zeta_array1[j] = zeta1
		int_theta1[j] = np.arccos(R1[2][2])
		int_phi1[j] = (np.arctan(-R1[2][0] / R1[2][1]))
		int_varphi1[j] = (np.arctan(R1[0][2] / R1[1][2]))

		T = ut.local_frame_surface(dzx2, dzy2, 1)
		R2 = np.dot(O, np.linalg.inv(T))
		if R2[2][2] < -1: R2[2][2] = -1.0
		elif R2[2][2] > 1: R2[2][2] = 1.0
		zeta_array2[j] = zeta2
		int_theta2[j] = np.arccos(R2[2][2])
		int_phi2[j] = (np.arctan(-R2[2][0] / R2[2][1]))
		int_varphi2[j] = (np.arctan(R2[0][2] / R2[1][2]))

		index1 = int((z + DIM[2]/2) * nslice / DIM[2]) % nslice
		int_index11 = int((zeta1 + DIM[2]/2) * nslice / DIM[2]) % nslice
		int_index12 = int((zeta2 + DIM[2]/2) * nslice / DIM[2]) % nslice


	with file('{}/DATA/EULER/{}_{}_{}_ANGLE.txt'.format(directory, model.lower(), csize, image), 'w') as outfile:
		np.savetxt(outfile, (z_array, theta, phi, varphi), fmt='%-12.6f')
	with file('{}/DATA/INTEULER/{}_{}_{}_{}_ANGLE1.txt'.format(directory, model.lower(), csize,  nm, image), 'w') as outfile:
		np.savetxt(outfile, (zeta_array1, int_theta1, int_phi1, int_varphi1), fmt='%-12.6f')
	with file('{}/DATA/INTEULER/{}_{}_{}_{}_ANGLE2.txt'.format(directory, model.lower(), csize, nm, image), 'w') as outfile:
		np.savetxt(outfile, (zeta_array2, int_theta2, int_phi2, int_varphi2), fmt='%-12.6f')

	if make_dxdy:
		with file('{}/DATA/INTPOS/{}_{}_{}_{}_INTDXDY_MOL.txt'.format(directory, model.lower(), csize, nm, image), 'w') as outfile:
			np.savetxt(outfile, (dxdyz_mol), fmt='%-12.6f')

	return z_array, theta, phi, varphi, zeta_array1, int_theta1, int_phi1, int_varphi1, zeta_array2, int_theta2, int_phi2, int_varphi2


def angle_dist(directory, model, csize, nimage, nmol, nsite, COM, DIM, nslice, nm, npi, ow_angles):

	print "BUILDING ANGLE DISTRIBUTIONS"

	dpi = np.pi / npi
	P_z_theta_phi = np.zeros((nslice,npi,npi*2))
	int_P_z_theta_phi_1 = np.zeros((nslice,npi,npi*2))
	int_P_z_theta_phi_2 = np.zeros((nslice,npi,npi*2))

	for image in xrange(nimage):
		sys.stdout.write("CREATING ANGLE POPULATION GRID from {} out of {} images\r".format(image, nimage) )
		sys.stdout.flush()

		if ow_angles:
			angles = mol_angles(directory, nimage, nslice, nmol, model, csize, COM, DIM, nsite, nm)
			z_array, theta, phi, varphi, zeta_array1, int_theta1, int_phi1, int_varphi1, zeta_array2, int_theta2, int_phi2, int_varphi2 = angles
		else:
			try:
				with file('{}/DATA/EULER/{}_{}_{}_ANGLE.txt'.format(directory, model.lower(), csize, image), 'r') as infile:
					z_array, theta, phi, varphi = np.loadtxt(infile)
				with file('{}/DATA/INTEULER/{}_{}_{}_{}_ANGLE1.txt'.format(directory, model.lower(), csize, nm, image), 'r') as infile:
					zeta_array1, int_theta1, int_phi1, int_varphi1 = np.loadtxt(infile)
				with file('{}/DATA/INTEULER/{}_{}_{}_{}_ANGLE2.txt'.format(directory, model.lower(), csize, nm, image), 'r') as infile:
					zeta_array2, int_theta2, int_phi2, int_varphi2 = np.loadtxt(infile)

			except Exception: 
				angles = mol_angles(directory, image, nslice, nmol, model, csize, COM, DIM, nsite, nm)
				z_array, theta, phi, varphi, zeta_array1, int_theta1, int_phi1, int_varphi1, zeta_array2, int_theta2, int_phi2, int_varphi2 = angles

		for j in xrange(nmol):
			
			z = z_array[j] + DIM[2]/2.
			index1 = int(z * nslice / DIM[2]) % nslice
			index2 = int(theta[j] / dpi)
			index3 = int((abs(phi)[j] + np.pi / 2.) / dpi) 

			try: P_z_theta_phi[index1][index2][index3] += 1
			except IndexError: pass
	
			z = zeta_array1[j] + DIM[2]/2.
			index1 = int(z * nslice / DIM[2]) % nslice
			index2 = int(int_theta1[j] /dpi)
			index3 = int((int_phi1[j] + np.pi / 2.) / dpi) 

			try: int_P_z_theta_phi_1[index1][index2][index3] += 1
			except IndexError: pass

			z = zeta_array2[j] + DIM[2]/2.
			index1 = int(z * nslice / DIM[2]) % nslice
			index2 = int(int_theta2[j] / dpi)
			index3 = int((int_phi2[j] + np.pi / 2.) / dpi)  

			try: int_P_z_theta_phi_2[index1][index2][index3] += 1
			except IndexError: pass

	
	print ""
	print "NORMALISING GRID"
	for index1 in xrange(nslice): 
		if np.sum(P_z_theta_phi[index1]) != 0:
			P_z_theta_phi[index1] = P_z_theta_phi[index1] / np.sum(P_z_theta_phi[index1])
		if np.sum(int_P_z_theta_phi_1[index1]) != 0:
			int_P_z_theta_phi_1[index1] = int_P_z_theta_phi_1[index1] / np.sum(int_P_z_theta_phi_1[index1])
		if np.sum(int_P_z_theta_phi_2[index1]) != 0:
			int_P_z_theta_phi_2[index1] = int_P_z_theta_phi_2[index1] / np.sum(int_P_z_theta_phi_2[index1])


	P_z_phi_theta = np.rollaxis(np.rollaxis(P_z_theta_phi, 2), 1)
	int_P_z_phi_theta_1 = np.rollaxis(np.rollaxis(int_P_z_theta_phi_1, 2), 1)
	int_P_z_phi_theta_2 = np.rollaxis(np.rollaxis(int_P_z_theta_phi_2, 2), 1)
	
	X_theta = np.arange(0, np.pi, dpi)
	X_phi = np.arange(-np.pi / 2, np.pi / 2, dpi)

	av_theta = np.zeros(nslice)
	av_phi = np.zeros(nslice)
	P1 = np.zeros(nslice)
	P2 = np.zeros(nslice)

	int_av_theta1 = np.zeros(nslice)
	int_av_phi1 = np.zeros(nslice)
	int_P11 = np.zeros(nslice)
	int_P21 = np.zeros(nslice)

	int_av_theta2 = np.zeros(nslice)
	int_av_phi2 = np.zeros(nslice)
	int_P12 = np.zeros(nslice)
	int_P22 = np.zeros(nslice)
	
	print "BUILDING AVERAGE ANGLE PROFILES"

	for index1 in xrange(nslice):
		sys.stdout.write("PROCESSING AVERAGE ANGLE PROFILES {} out of {} slices\r".format(index1, nslice) )
		sys.stdout.flush() 

		for index2 in xrange(npi):
			av_theta[index1] += np.sum(P_z_theta_phi[index1][index2]) * X_theta[index2]
			P1[index1] += np.sum(P_z_phi_theta[index1][index2]) * np.cos(X_theta[index2])
			P2[index1] += np.sum(P_z_phi_theta[index1][index2]) * 0.5 * (3 * np.cos(X_theta[index2])**2 - 1)

			int_av_theta1[index1] += np.sum(int_P_z_theta_phi_1[index1][index2]) * X_theta[index2] 
			int_P11[index1] += np.sum(int_P_z_theta_phi_1[index1][index2]) * np.cos(X_theta[index2])
			int_P21[index1] += np.sum(int_P_z_theta_phi_1[index1][index2]) * 0.5 * (3 * np.cos(X_theta[index2])**2 - 1)

			int_av_theta2[index1] += np.sum(int_P_z_theta_phi_2[index1][index2]) * X_theta[index2] 
			int_P12[index1] += np.sum(int_P_z_theta_phi_2[index1][index2]) * np.cos(X_theta[index2])
			int_P22[index1] += np.sum(int_P_z_theta_phi_2[index1][index2]) * 0.5 * (3 * np.cos(X_theta[index2])**2 - 1)

			av_phi[index1] += np.sum(P_z_phi_theta[index1][index2]) * (X_phi[index2])  
			int_av_phi1[index1] += np.sum(int_P_z_phi_theta_1[index1][index2]) * (X_phi[index2]) 
			int_av_phi2[index1] += np.sum(int_P_z_phi_theta_2[index1][index2]) * (X_phi[index2]) 

	a_dist = (av_theta, av_phi, P1, P2, int_av_theta1, int_av_phi1, int_P11, int_P21, int_av_theta2, int_av_phi2, int_P12, int_P22)
	
	return a_dist


def polarisability(directory, model, csize, nimage, nmol, nsite, COM, DIM, nslice, nm, npi, a, counts, ow_polar):


	av_O = np.zeros((nslice, 9))
	av_int_O1 = np.zeros((nslice, 9))
	av_int_O2 = np.zeros((nslice, 9))

	for image in xrange(nimage):
		sys.stdout.write("CREATING ROTATIONAL TENSOR PROFILE from {} out of {} images\r".format(image, nimage) )
		sys.stdout.flush()
		if ow_polar: temp_O, temp_int_O1, temp_int_O2 = R_tensors(directory, image, nslice, nmol, model, csize, COM, DIM, nsite, nm)
		else: 
			try:
				with file('{}/DATA/EULER/{}_{}_{}_{}_ODIST.txt'.format(directory, model.lower(), csize, nslice, image), 'r') as infile:
					temp_O = np.loadtxt(infile)
				with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_ODIST1.txt'.format(directory, model.lower(), csize, nslice, nm, image), 'r') as infile:
					temp_int_O1 = np.loadtxt(infile)
				with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_ODIST2.txt'.format(directory, model.lower(), csize, nslice, nm, image), 'r') as infile:
					temp_int_O2 = np.loadtxt(infile)

			except Exception: temp_O, temp_int_O1, temp_int_O2 = R_tensors(directory, image, nslice, nmol, model, csize, COM, DIM, nsite, nm)

		av_O += temp_O
		av_int_O1 += temp_int_O1
		av_int_O2 += temp_int_O2

	count_O, count_int_O1, count_int_O2 = counts

	axx = np.zeros(nslice)
	azz = np.zeros(nslice)

	int_axx1 = np.zeros(nslice)
	int_azz1 = np.zeros(nslice)

	int_axx2 = np.zeros(nslice)
	int_azz2 = np.zeros(nslice)

	vd = DIM[0] * DIM[1] * DIM[2] / nslice

	for n in xrange(nslice):
		if count_O[n] != 0:
			av_O[n] *= 1./ count_O[n]
			for j in xrange(3):
				axx[n] += a[j] * 0.5 * (av_O[n][j] + av_O[n][j+3]) 
				azz[n] += a[j] * av_O[n][j+6]
		else:
			axx[n] = np.mean(a)					
			azz[n] = np.mean(a)

		if count_int_O1[n] != 0:
			av_int_O1[n] *= 1./ count_int_O1[n]
			for j in xrange(3):
				int_axx1[n] += a[j] * 0.5 * (av_int_O1[n][j] + av_int_O1[n][j+3]) 
				int_azz1[n] += a[j] * av_int_O1[n][j+6] 

		else: 					
			int_axx1[n] = np.mean(a)					
			int_azz1[n] = np.mean(a)

		if count_int_O2[n] != 0:
			av_int_O2[n] *= 1./ count_int_O2[n]
			for j in xrange(3):
				int_axx2[n] += a[j] * 0.5 * (av_int_O2[n][j] + av_int_O2[n][j+3]) 
				int_azz2[n] += a[j] * av_int_O2[n][j+6] 
		else: 
			int_axx2[n] = np.mean(a)					
			int_azz2[n] = np.mean(a)

	polar = (axx, azz, int_axx1, int_azz1, int_axx2, int_azz2)

	return polar

def euler_profile(directory, nimage, nslice, nmol, model, csize, suffix, AT, Q, M, LJ, COM, DIM, nsite, a_type, nm, ow_angles, ow_polar):
		

	print ""
	print "CALCULATING ORIENTATIONS OF {} {} SIZE {}\n".format(model.upper(), suffix.upper(), csize)	

	npi = 50
	dpi = np.pi / npi

	q1 = np.zeros(nslice)
	q2 = np.zeros(nslice)
	int_q11 = np.zeros(nslice)
	int_q12 = np.zeros(nslice)
	int_q21 = np.zeros(nslice)
	int_q22 = np.zeros(nslice)

	av_varphi = np.zeros(nslice)
	int_av_varphi1 = np.zeros(nslice)
	int_av_varphi2 = np.zeros(nslice)

	water_au_A = 0.5291772083
	bohr_to_A = 0.529**3

	water_ame_a = [1.672, 1.225, 1.328]
	water_abi_a = [1.47, 1.38, 1.42]
	water_exp_a = [1.528, 1.415, 1.468]

	"Calculated polarisbilities taken from NIST Computational Chemistry Comparison and Benchmark DataBase (CCCBDB)" 
	methanol_calc_a = [3.542, 3.0124, 3.073]  #B3LYP/aug-cc-pVQZ
	ethanol_calc_a = [5.648, 4.689, 5.027]  #B3LYP/Sadlej_pVTZ
	dmso_calc_a = [6.824, 8.393, 8.689]  #B3PW91/aug-cc-pVTZ

	if model.upper() == 'METHANOL':
		if a_type == 'calc': a = methanol_calc_a
	if model.upper() == 'ETHANOL':
                if a_type == 'calc': a = ethanol_calc_a
	if model.upper() == 'DMSO':
                if a_type == 'calc': a = dmso_calc_a
	else:
		if a_type == 'exp': a = water_exp_a
		elif a_type == 'ame': a = water_ame_a
		elif a_type == 'abi': a = water_abi_a

	Z1 = np.linspace(0, DIM[2], nslice)
	Z2 = np.linspace(-1/2.*DIM[2], 1/2.*DIM[2], nslice)

	with file('{}/DATA/DEN/{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, nimage), 'r') as infile:
		av_density = np.loadtxt(infile)

	with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, nm, nimage), 'r') as infile:
		int_av_density = np.loadtxt(infile)

	count_O = av_density[-1] * nimage * DIM[0] * DIM[1] * DIM[2] / nslice
	count_int_O1 = int_av_density[-4] * nimage * DIM[0] * DIM[1] * DIM[2] / nslice
	count_int_O2 = int_av_density[-3][::-1] * nimage * DIM[0] * DIM[1] * DIM[2] / nslice

	counts = (count_O, count_int_O1, count_int_O2)
	axx, azz, int_axx1, int_azz1, int_axx2, int_azz2 = polarisability(directory, model, csize, nimage, nmol, nsite, COM, DIM, nslice, nm, npi, a, counts, ow_polar)

	plt.figure(0)
	plt.plot(Z1, axx)
	plt.plot(Z1, azz)
	plt.figure(1)
	plt.plot(Z2, int_axx1)
	plt.plot(Z2, int_azz1)
	plt.show()

	av_theta, av_phi, P1, P2, int_av_theta1, int_av_phi1, int_P11, int_P21, int_av_theta2, int_av_phi2, int_P12, int_P22 = angle_dist(directory, model, csize, nimage, nmol, nsite, COM, DIM, nslice, nm, npi, ow_angles)	

	print ""
	print "WRITING TO FILE..."

	with file('{}/DATA/EULER/{}_{}_{}_{}_{}_EUL.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage), 'w') as outfile:
		np.savetxt(outfile, (axx, azz, av_theta, av_phi, av_varphi, P1, P2), fmt='%-12.6f')
	with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_{}_EUL1.txt'.format(directory, model.lower(), csize, nslice, a_type, nm, nimage), 'w') as outfile:
		np.savetxt(outfile, (int_axx1, int_azz1, int_av_theta1, int_av_phi1,int_av_varphi1,int_P11, int_P21), fmt='%-12.6f')
	with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_{}_EUL2.txt'.format(directory, model.lower(), csize, nslice, a_type, nm, nimage), 'w') as outfile:
		np.savetxt(outfile, (int_axx2[::-1], int_azz2[::-1], int_av_theta2, int_av_phi2,int_av_varphi2,int_P12,int_P22), fmt='%-12.6f')
							
	print "{} {} {} COMPLETE\n".format(directory, model.upper(), csize)


"""
print "BUILDING POLARISABILITY PROFILES"
for index1 in xrange(nslice):
	sys.stdout.write("PROCESSING POLARISABILITIES {} out of {} slices\r".format(index1, nslice) )
	sys.stdout.flush()
	for index2, theta in enumerate(X_theta):
		for index3, phi in enumerate(X_phi):

			axx[index1] += (a[0] * (np.cos(theta)**2 * np.cos(phi)**2 + np.sin(phi)**2) 
			+ a[1] * (np.cos(theta)**2 * np.sin(phi)**2 + np.cos(phi)**2) 
			+ a[2] * np.sin(theta)**2) * P_z_theta_phi[index1][index2][index3] * 0.5 * dpi**2

			azz[index1] += (a[0] * np.sin(theta)**2 * np.cos(phi)**2 
			+ a[1] * np.sin(theta)**2 * np.sin(phi)**2 
			+ a[2] * np.cos(theta)**2) * P_z_theta_phi[index1][index2][index3] * dpi**2

			int_axx1[index1] += (a[0] * (np.cos(theta)**2 * np.cos(phi)**2 + np.sin(phi)**2) 
			+ a[1] * (np.cos(theta)**2 * np.sin(phi)**2 + np.cos(phi)**2) 
			+ a[2] * np.sin(theta)**2) * int_P_z_theta_phi_1[index1][index2][index3] * 0.5 * dpi**2

			int_azz1[index1] += (a[0] * np.sin(theta)**2 * np.cos(phi)**2 
			+ a[1] * np.sin(theta)**2 * np.sin(phi)**2 
			+ a[2] * np.cos(theta)**2) * int_P_z_theta_phi_1[index1][index2][index3] * dpi**2

			int_axx2[index1] += (a[0] * (np.cos(theta)**2 * np.cos(phi)**2 + np.sin(phi)**2) 
			+ a[1] * (np.cos(theta)**2 * np.sin(phi)**2 + np.cos(phi)**2) 
			+ a[2] * np.sin(theta)**2) * int_P_z_theta_phi_2[index1][index2][index3] * 0.5 * dpi**2

			int_azz2[index1] += (a[0] * np.sin(theta)**2 * np.cos(phi)**2 
			+ a[1] * np.sin(theta)**2 * np.sin(phi)**2 
			+ a[2] * np.cos(theta)**2) * int_P_z_theta_phi_2[index1][index2][index3] * dpi**2

		q1[index1] += (3 * np.cos(theta)**2 - 1) * np.sum(P_z_theta_phi[index1][index2]) * av_density[-1][index1] * 0.5 * np.pi / npi
		q2[index1] += P2[index1] * av_density[-1][index1] * np.pi / npi

		int_q11[index1] += (3 * np.cos(theta)**2 - 1) * np.sum(int_P_z_theta_phi_1[index1][index2]) * int_av_density[-4][index1] * 0.5 * np.pi / npi
		int_q21[index1] += P2[index1] * int_av_density[-4][index1] * np.pi / npi

		int_q12[index1] += (3 * np.cos(theta)**2 - 1) * np.sum(int_P_z_theta_phi_2[index1][index2]) * int_av_density[-3][index1] * 0.5 * np.pi / npi
		int_q22[index1] += P2[index1] * int_av_density[-3][index1] * np.pi / npi
"""

#test_orientation()
