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

def surface_ne(root, model, csize, nm, nxy, int_exx, int_ezz, DIM, nimage, thetai, zR):

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
				angle1[i][j][k] = np.arccos(np.dot(K, normal_vector(Eta1[j][k], Dx1[j][k], Dy1[j][k], DIM, zR[i])))
				angle2[i][j][k] = np.arccos(np.dot(K, normal_vector(Eta2[j][k], Dx2[j][k], Dy2[j][k], DIM, zR[i])))

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

def dielectric_refractive_index(root, model, csize, nslice, nimage, a_type, force, nm, nxy, DIM, ow_A):

	print "PROCESSING DIELECTRIC AND REFRACTIVE INDEX PROFILES\n"

	with file('{}/DATA/DEN/{}_{}_{}_{}_DEN.txt'.format(root, model.lower(), csize, nslice, nimage), 'r') as infile:
		av_mass_den, av_atom_den, av_mol_den, av_H_den = np.loadtxt(infile)

	with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt'.format(root, model.lower(), csize, nslice, nm, nimage), 'r') as infile:
		int_av_mass_den, int_av_atom_den, int_av_mol_den, int_av_H_den, w_den_1, w_den_2 = np.loadtxt(infile)

	with file('{}/DATA/EULER/{}_{}_{}_{}_{}_EUL.txt'.format(root, model.lower(), csize, nslice, a_type, nimage), 'r') as infile:
		axx, azz, _, _, _, _, _, _, _ = np.loadtxt(infile)

	with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_{}_EUL.txt'.format(root, model.lower(), csize, nslice, a_type, nm, nimage), 'r') as infile:
		int_axx, int_azz, _, _, _, _, _, _, _ = np.loadtxt(infile)

	with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_{}_EUL1.txt'.format(root, model.lower(), csize, nslice, a_type, nm, nimage), 'r') as infile:
		int_axx1, int_azz1, _, _, _, _, _, _, _ = np.loadtxt(infile)

	with file('{}/DATA/INTEULER/{}_{}_{}_{}_{}_{}_EUL2.txt'.format(root, model.lower(), csize, nslice, a_type, nm, nimage), 'r') as infile:
		int_axx2, int_azz2, _, _, _, _, _, _, _ = np.loadtxt(infile)

	with file('{}/DATA/DEN/{}_{}_{}_COM.txt'.format(root, model.lower(), csize, nimage), 'r') as infile:
		xR, yR, zR = np.loadtxt(infile)
		if nimage ==1: zR = [zR]
	
	with file('{}/DATA/DEN/{}_{}_{}_{}_PAR.txt'.format(root, model.lower(), csize, nslice, nimage), 'r') as infile:
		param = np.loadtxt(infile)

	Z = np.linspace(0, DIM[2], nslice)
	int_Z = np.linspace(-DIM[2]/2., DIM[2]/2., nslice)

	dz = DIM[2] / nslice
	#density = map (lambda z: ut.den_func(z, param[0], param[1], param[2], param[3], param[4]) * con.N_A / np.sum(M) * 1E-24 , Z)

	ur = 1 #- 9E-6
	angle = 52.9*np.pi/180.
	DEN = av_mol_den
	INT_DEN = int_av_mol_den

	exx = map( lambda n: (1 + 8 * np.pi / 3. * DEN[n] * axx[n]) / (1 - 4 * np.pi / 3. * DEN[n] * axx[n]), range(nslice))
	ezz = map( lambda n: (1 + 8 * np.pi / 3. * DEN[n] * azz[n]) / (1 - 4 * np.pi / 3. * DEN[n] * azz[n]), range(nslice))

	no = map (lambda n: np.sqrt(ur * exx[n]), range(nslice))
	anis = map (lambda n: 1 - (ezz[n] - exx[n]) * np.sin(angle)**2 / ezz[n], range(nslice))
	ne = map (lambda n: np.sqrt(ur * exx[n] / anis[n]), range(nslice))
	ni = map (lambda n: np.sqrt(ur * ezz[n]), range(nslice))

	int_exx = map( lambda n: (1 + 8 * np.pi / 3. * INT_DEN[n] * int_axx[n]) / (1 - 4 * np.pi / 3. * INT_DEN[n] * int_axx[n]), range(nslice))
	int_ezz = map( lambda n: (1 + 8 * np.pi / 3. * INT_DEN[n] * int_azz[n]) / (1 - 4 * np.pi / 3. * INT_DEN[n] * int_azz[n]), range(nslice))

	int_no = map (lambda n: np.sqrt(ur * int_exx[n]), range(nslice))
	int_anis = map (lambda n: 1 - (int_ezz[n] - int_exx[n]) * np.sin(angle)**2 / int_ezz[n], range(nslice))
	int_ne = map (lambda n: np.sqrt(ur * int_exx[n] / anis[n]), range(nslice))
	int_ni = map (lambda n: np.sqrt(ur * int_ezz[n]), range(nslice))

	"""
	plt.plot(Z, w_den_1, color='b')
	plt.plot(Z, w_den_2, color='r')
	plt.show()

	plt.scatter(int_Z, int_axx, color='b')
	plt.scatter(int_Z, int_azz, color='r')
	plt.show()
	"""
	T_w_axx_den1 = np.zeros(nslice)
	T_w_azz_den1 = np.zeros(nslice)
	
	T_w_axx_den2 = np.zeros(nslice)
	T_w_azz_den2 = np.zeros(nslice)

	print "BUILDING POLARISABILITY PROFILE"
	for i in xrange(nimage):
		sys.stdout.write("PROCESSING {} out of {} IMAGES\r".format(i+1, nimage) )
		sys.stdout.flush()

		if os.path.exists('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_ACOUNT.txt'.format(root, model.lower(), csize, nslice, nm, nxy, i)) and ow_A.upper() != "Y":
			with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_ACOUNT.txt'.format(root, model.lower(), csize, nslice, nm, nxy, i)) as infile:
				w_axx_den1, w_azz_den1, w_axx_den2, w_azz_den2 = np.loadtxt(infile)
			T_w_axx_den1 += w_axx_den1 / nimage 
			T_w_azz_den1 += w_azz_den1 / nimage

			T_w_axx_den2 += w_axx_den2 / nimage 
			T_w_azz_den2 += w_azz_den2 / nimage 

		else:
			w_axx_den1 = np.zeros(nslice)
			w_azz_den1 = np.zeros(nslice)

			w_axx_den2 = np.zeros(nslice)
			w_azz_den2 = np.zeros(nslice)

			with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_CURVE.npz'.format(root, model.lower(), csize, nm, nxy, i), 'r') as infile:
				npzfile = np.load(infile)
				XI1 = npzfile['XI1']
				XI2 = npzfile['XI2']
			for n in xrange(nslice):
				z = int_Z[n]
				#if z < 0:
				for j in xrange(nxy):
					for k in xrange(nxy):
						dz = z - XI1[j][k]
						m = int((dz+DIM[2]/2.) * nslice / DIM[2]) % nslice
						w_axx_den1[n] += int_axx1[m] * w_den_1[n] / ( nxy**2 )
						w_azz_den1[n] += int_azz1[m] * w_den_1[n] / ( nxy**2 )
				#else:
				#for j in xrange(nxy):
				#for k in xrange(nxy):
						dz =  XI2[j][k] - z
						m = int((dz+DIM[2]/2.) * nslice / DIM[2]) % nslice
						w_axx_den2[n] += int_axx2[m] * w_den_2[n] / ( nxy**2 )
						w_azz_den2[n] += int_azz2[m] * w_den_2[n] / ( nxy**2 )

			T_w_axx_den1 += w_axx_den1 / nimage 
			T_w_azz_den1 += w_azz_den1 / nimage 

			T_w_axx_den2 += w_axx_den2 / nimage 
			T_w_azz_den2 += w_azz_den2 / nimage 

			with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_ACOUNT.txt'.format(root, model.lower(), csize, nslice, nm, nxy, i), 'w') as outfile:
				np.savetxt(outfile, (w_axx_den1, w_azz_den1, w_axx_den2, w_azz_den2), fmt='%-12.6f')

	print "\n"

	int_exx1 = map( lambda n: (1 + 8 * np.pi / 3. * T_w_axx_den1[n]) / (1 - 4 * np.pi / 3. * T_w_axx_den1[n]), range(nslice))
	int_ezz1 = map( lambda n: (1 + 8 * np.pi / 3. * T_w_azz_den1[n]) / (1 - 4 * np.pi / 3. * T_w_azz_den1[n]), range(nslice))

	int_exx2 = map( lambda n: (1 + 8 * np.pi / 3. * T_w_axx_den2[n]) / (1 - 4 * np.pi / 3. * T_w_axx_den2[n]), range(nslice))
	int_ezz2 = map( lambda n: (1 + 8 * np.pi / 3. * T_w_azz_den2[n]) / (1 - 4 * np.pi / 3. * T_w_azz_den2[n]), range(nslice))

	int_no1 = map (lambda n: np.sqrt(ur * int_exx1[n]), range(nslice))
	#int_anis = surface_ne(root, model, csize, nm, nxy, int_exx, int_ezz, DIM, nimage, angle, zR)
	int_anis = map (lambda n: 1 - (int_ezz1[n] - int_exx1[n]) * np.sin(angle)**2 / int_ezz1[n], range(nslice))
	int_ne1 = map (lambda n: np.sqrt(ur * int_exx1[n] / int_anis[n]), range(nslice))
	int_ni1 = map (lambda n: np.sqrt(ur * int_ezz1[n]), range(nslice))

	int_no2 = map (lambda n: np.sqrt(ur * int_exx2[n]), range(nslice))
	#int_anis = surface_ne(root, model, csize, nm, nxy, int_exx, int_ezz, DIM, nimage, angle, zR)
	int_anis = map (lambda n: 1 - (int_ezz2[n] - int_exx2[n]) * np.sin(angle)**2 / int_ezz2[n], range(nslice))
	int_ne2 = map (lambda n: np.sqrt(ur * int_exx2[n] / int_anis[n]), range(nslice))
	int_ni2 = map (lambda n: np.sqrt(ur * int_ezz2[n]), range(nslice))

	print "WRITING TO FILE..."

	with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_DEN.txt'.format(root, model.lower(), csize, nslice, a_type, nimage), 'w') as outfile:
		np.savetxt(outfile, (exx,ezz,no,ne,ni), fmt='%-12.6f')
	with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_INTDEN.txt'.format(root, model.lower(), csize, nslice, a_type, nm, nimage), 'w') as outfile:
		np.savetxt(outfile, (int_exx,int_ezz,int_no,int_ne,int_ni), fmt='%-12.6f')
	with file('{}/DATA/DIELEC/{}_{}_{}_{}_{}_{}_WINTDEN.txt'.format(root, model.lower(), csize, nslice, a_type, nm, nimage), 'w') as outfile:
		np.savetxt(outfile, (int_exx1,int_ezz1,int_no1,int_ne1,int_ni1,int_exx2,int_ezz2,int_no2,int_ne2,int_ni2), fmt='%-12.6f')

	print "{} {} {} COMPLETE\n".format(root, model.upper(), csize)


def main(root, model, nsite, AT, Q, M, LJ, T, cutoff, csize, TYPE, folder, nfolder, suffix, ntraj):


	lslice = 0.05 * LJ[1]
	vlim = 3
	ncube = 3

	T = int(raw_input("Temperature: (K) "))
	cutoff = int(raw_input("Cutoff: (A) "))

	CSIZE = []
	nimage = int(raw_input("Number of images: "))
	ndim = int(raw_input("No. of dimensions: "))

	force = raw_input("VDW Force corrections? (Y/N): ")
	if force.upper() == 'Y': folder = 'SURFACE_2'
	else: folder = 'SURFACE' 
	suffix = 'surface'
	nxy = 30

	a_type = raw_input("Polarisability Parameter type? (exp, ame, abi)?: ")	

	for i in xrange(ndim):
		CSIZE.append(5 * i + 50)
		if model.upper() == 'ARGON': root = '/data/fl7g13/AMBER/{}/T_{}_K/CUT_{}_A/{}_{}/{}'.format(model.upper(), T, cutoff, model.upper(), CSIZE[i], folder.upper())
		else: root = '/data/fl7g13/AMBER/WATER/{}/T_{}_K/CUT_{}_A/{}_{}/{}'.format(model.upper(), T, cutoff, model.upper(), CSIZE[i], folder.upper())
		
		natom, nmol, DIM = ut.read_atom_mol_dim("{}/{}_{}_{}0".format(root, model.lower(), CSIZE[i], suffix))

		nslice = int(DIM[2] / lslice)
		nm = int(DIM[0] / (LJ[1]))

		if not os.path.exists("{}/DATA/DIELEC".format(root)): os.mkdir("{}/DATA/DIELEC".format(root))
		if os.path.exists('{}/DATA/DIELEC/{}_{}_{}_{}_{}_DEN.txt'.format(root, model.lower(), CSIZE[i], nslice, a_type, nimage)):
			print '\nFILE FOUND {}/DATA/DIELEC/{}_{}_{}_{}_{}_DEN.txt'.format(root, model.lower(), CSIZE[i], nslice, a_type, nimage)
			overwrite = raw_input("OVERWRITE? (Y/N): ")
			if overwrite.upper() == 'Y':  
				ow_A = raw_input("OVERWRITE ACOUNT? (Y/N): ") 
				dielectric_refractive_index(root, model, CSIZE[i], nslice, nimage, a_type, force, nm, nxy, DIM, ow_A)
		else: dielectric_refractive_index(root, model, CSIZE[i], nslice, nimage, a_type, force, nm, nxy, DIM, 'Y')



