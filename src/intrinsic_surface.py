"""
*************** POSITION ANALYSIS *******************

PROGRAM INPUT:
	       

PROGRAM OUTPUT: 
		
		

***************************************************************
Created 11/12/15 by Frank Longford

Last modified 10/05/16 by Frank Longford
"""

import numpy as np
import scipy as sp
import subprocess, time, sys, os, math, copy, gc
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

#from mpi4py import MPI

def intrinsic_surface(traj, root, model, csize, suffix, nsite, ncube, DIM, vlim, sigma, M, nm, image, nimage, com, ow_coeff):
	"Creates intrinsic surface of image." 

	phi = 5E-2
	tau = 0.4 * sigma	
	if model.upper() == 'TIP4P2005': c = 1.1
	else: c = 0.8
	n0 = int(DIM[0] * DIM[1] * c / sigma**2)

	ZYX = np.rot90(traj.xyz[image])
	zat = ZYX[0] * 10
	yat = ZYX[1] * 10
	xat = ZYX[2] * 10

	xmol, ymol, zmol = ut.molecules(xat, yat, zat, nsite, M, com)
	_, _, zcom = ut.centre_mass(xat, yat, zat, nsite, M)
	natom = len(xat)
	nmol = natom / nsite

	if os.path.exists('{}/DATA/ACOEFF/{}_{}_{}_{}_PIVOTS.txt'.format(root, model.lower(), csize, nm, image)) and ow_coeff.upper() != 'Y':
	   	with file('{}/DATA/ACOEFF/{}_{}_{}_{}_INTCOEFF.txt'.format(root, model.lower(), csize, nm, image), 'r') as infile: 
			auv1, auv2 = np.loadtxt(infile)
		with file('{}/DATA/ACOEFF/{}_{}_{}_{}_PIVOTS.txt'.format(root, model.lower(), csize, nm, image), 'r') as infile:
			piv_n1, piv_n2 = np.loadtxt(infile)
	else:
		sys.stdout.write("PROCESSING {} INTRINSIC SURFACE {} \n".format(root, image+1) )
		sys.stdout.flush()
		auv1, auv2, piv_n1, piv_n2 = build_surface(xmol, ymol, zmol, DIM, nmol, ncube, sigma, nm, n0, vlim, phi, zcom, tau)
	
	with file('{}/DATA/ACOEFF/{}_{}_{}_{}_INTCOEFF.txt'.format(root, model.lower(), csize, nm, image), 'w') as outfile:
		np.savetxt(outfile, (auv1, auv2), fmt='%-12.6f')

	with file('{}/DATA/ACOEFF/{}_{}_{}_{}_PIVOTS.txt'.format(root, model.lower(), csize, nm, image), 'w') as outfile:
		np.savetxt(outfile, (piv_n1, piv_n2), fmt='%-12.6f')

	gc.collect()

	return auv1, auv2, piv_n1, piv_n2


def build_surface(xmol, ymol, zmol, DIM, nmol, ncube, sigma, nm, n0, vlim, phi, zcom, tau):

	mol_list = range(nmol)
	piv_n1 = range(ncube**2)
	piv_z1 = np.zeros(ncube**2)
	piv_n2 = range(ncube**2)
	piv_z2 = np.zeros(ncube**2)
	new_pivots1 = []
	new_pivots2 = []

	for n in xrange(nmol):
		vapour = 0
		for m in xrange(nmol):
			dr2 = (xmol[n] - xmol[m])**2 + (ymol[n] - ymol[m])**2 + (zmol[n] - zmol[m])**2			
			if n!= m and dr2 < (1.5*sigma)**2: vapour += 1
			if vapour > vlim:

				indexx = int(xmol[n] * ncube / DIM[0]) % ncube
                                indexy = int(ymol[n] * ncube / DIM[1]) % ncube

				if zmol[n] - zcom < piv_z1[ncube*indexx + indexy]:
					piv_n1[ncube*indexx + indexy] = n
					piv_z1[ncube*indexx + indexy] = zmol[n] - zcom

				elif zmol[n] - zcom > piv_z2[ncube*indexx + indexy]:
					piv_n2[ncube*indexx + indexy] = n
					piv_z2[ncube*indexx + indexy] = zmol[n] - zcom

				break
		if vapour <= vlim: mol_list.remove(n)

	print np.array(piv_n1), np.array(piv_n2)
	for n in piv_n1: 
		mol_list.remove(n)
		new_pivots1.append(n)
	for n in piv_n2:
		mol_list.remove(n)
		new_pivots2.append(n)

	lpiv1 = len(new_pivots1)
	lpiv2 = len(new_pivots2)

	start = time.time()

	diag = np.diagflat([4*np.pi**2*((int(j/(2*nm+1))-nm)**2 + (int(j%(2*nm+1))-nm)**2)* phi for j in xrange((2*nm+1)**2)])
	A1 = np.zeros(((2*nm+1)**2, (2*nm+1)**2)) + diag
	A2 = np.zeros(((2*nm+1)**2, (2*nm+1)**2)) + diag
	b1 = np.zeros((2*nm+1)**2)
	b2 = np.zeros((2*nm+1)**2)

	loop = 0
	while len(piv_n1) < n0 or len(piv_n2) < n0 and lpiv1 + lpiv2 > 0:

		start1 = time.time()

		if lpiv1 > 0: 
			fu1 = [[function(xmol[ns], int(j/(2*nm+1))-nm, DIM[0]) * function(ymol[ns], int(j%(2*nm+1))-nm, DIM[1]) for ns in new_pivots1] for j in xrange((2*nm+1)**2)]
			for k in xrange((2*nm+1)**2): b1[k] += np.sum([(zmol[new_pivots1[ns]]- zcom) * fu1[k][ns] for ns in xrange(len(new_pivots1))])
		if lpiv2 > 0: 
			fu2 = [[function(xmol[ns], int(j/(2*nm+1))-nm, DIM[0]) * function(ymol[ns], int(j%(2*nm+1))-nm, DIM[1]) for ns in new_pivots2] for j in xrange((2*nm+1)**2)]
			for k in xrange((2*nm+1)**2): b2[k] += np.sum([(zmol[new_pivots2[ns]]- zcom) * fu2[k][ns] for ns in xrange(len(new_pivots2))])

		end11 = time.time()

		for j in xrange((2*nm+1)**2):
			for k in xrange(j+1):
				if lpiv1 > 0:
					A1[j][k] += np.sum([fu1[k][ns] * fu1[j][ns] for ns in xrange(len(new_pivots1))])
					A1[k][j] = A1[j][k]
				if lpiv2 > 0:
					A2[j][k] += np.sum([fu2[k][ns] * fu2[j][ns] for ns in xrange(len(new_pivots2))])
					A2[k][j] = A2[j][k]

		end1 = time.time()

		if lpiv1 > 0:
			lu, piv  = sp.linalg.lu_factor(A1)
			auv1 = sp.linalg.lu_solve((lu, piv), b1)
		if lpiv2 > 0:
			lu, piv  = sp.linalg.lu_factor(A2)
			auv2 = sp.linalg.lu_solve((lu, piv), b2)

		end2 = time.time()

		if len(piv_n1) == n0 and len(piv_n2) == n0: 
			print 'Matrix calculation: {:7.3f} {:7.3f}  Decomposition: {:7.3f} {} {} {} {} {} '.format(end11 - start1, end1 - end11, end2 - end1, n0, len(piv_n1), len(piv_n2), lpiv1, lpiv2)
			break
	
		new_pivots1 = []
		new_pivots2 = []

		for n in mol_list:

			x = xmol[n]
			y = ymol[n]
			z = zmol[n] - zcom

			if z < 0:
				zeta = xi(x, y, nm, auv1, DIM)
				if len(piv_n1) < n0 and abs(zeta - z) <= tau:
					piv_n1.append(n)
					new_pivots1.append(n)
					mol_list.remove(n)
				elif abs(zeta - z) > 3.0 * sigma:
					mol_list.remove(n)					
			else:
				zeta = xi(x, y, nm, auv2, DIM)
				if len(piv_n2) < n0 and abs(zeta - z) <= tau:
					piv_n2.append(n)
					new_pivots2.append(n)
					mol_list.remove(n)
				elif abs(zeta - z) > 3.0 * sigma:
					mol_list.remove(n)
			if len(piv_n1) == n0 and len(piv_n2) == n0: break

		end3 = time.time()

		lpiv1 = len(new_pivots1)
		lpiv2 = len(new_pivots2)

		tau = tau *1.1
		loop += 1

		end = time.time()
		print 'Matrix calculation: {:7.3f} {:7.3f}  Decomposition: {:7.3f}  Pivot selection: {:7.3f}  LOOP time: {:7.3f}   {} {} {} {} {} '.format(end11 - start1, end1 - end11, end2 - end1, end3 - end2, end - start1, n0, len(piv_n1), len(piv_n2), lpiv1, lpiv2)			

	print 'TOTAL time: {:7.2f}  {} {}'.format(end - start, len(piv_n1), len(piv_n2))
	return auv1, auv2, piv_n1, piv_n2


def function(x, u, Lx):

	if u == 0: return 1
	elif u > 0: return np.cos(2 * np.pi * u * x / Lx)
	else: return np.sin(- 2 * np.pi * u * x / Lx)


def dfunction(x, u, Lx):

	if u == 0: return 0
	elif u > 0: return - 2 * np.pi * u / Lx * np.sin(2 * np.pi * u * x / Lx)
	else: return -2 * np.pi * u / Lx * np.cos(-2 * np.pi * u * x / Lx)


def ddfunction(x, u, Lx):

	if u == 0: return 0
	elif u > 0: return - 4 * np.pi**2 * u**2 / Lx**2 * np.cos(2 * np.pi * u * x / Lx)
	else: return - 4 * np.pi**2 * u**2 / Lx**2 * np.sin(-2 * np.pi * u * x / Lx)

def xi(x, y, nm, auv, DIM):

	zeta = 0
	for u in xrange(-nm,nm+1):
		for v in xrange(-nm, nm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			zeta += function(x, u, DIM[0]) * function(y, v, DIM[1]) * auv[j]
	return zeta


def dxyi(x, y, nm, auv, DIM):

	dzx = 0
	dzy = 0
	for u in xrange(-nm,nm+1):
		for v in xrange(-nm, nm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			dzx += dfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv[j]
			dzy += function(x, u, DIM[0]) * dfunction(y, v, DIM[1]) * auv[j]
	return dzx, dzy


def ddxyi(x, y, nm, auv, DIM):

	ddzx = 0
	ddzy = 0
	for u in xrange(-nm,nm+1):
		for v in xrange(-nm, nm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			ddzx += ddfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv[j]
			ddzy += function(x, u, DIM[0]) * ddfunction(y, v, DIM[1]) * auv[j]
	return ddzx, ddzy


def slice_area(auv, nm, z):

        Axi = 0
        for j in xrange((2*nm+1)**2):
                xi2 = np.real(auv[j]*np.conj(auv[j]))
                Axi += xi2 / (1 + xi2 * abs(z) * j**2)**2
        return 1 + 0.5*Axi


def intrinsic_density(traj, root, model, csize, suffix, nm, image, nslice, nsite, AT, DIM, M, nxy, auv1, auv2, com, ow_count):
	"Saves atom, mol and mass intrinsic profiles  ntraj number of trajectory snapshots" 
	
	if os.path.exists('{}/DATA/INTDEN/{}_{}_{}_{}_{}_COUNT.txt'.format(root, model.lower(), csize, nslice, nm, image)) and ow_count.upper() != 'Y':
		with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_COUNT.txt'.format(root, model.lower(), csize, nslice, nm, image)) as infile:
			mass_count, atom_count, mol_count, H_count = np.loadtxt(infile)
			
	else:
		sys.stdout.write("PROCESSING {} INTRINSIC DENSITY {} \r".format(root, image) )
		sys.stdout.flush()

		ZYX = np.rot90(traj.xyz[image])
		zat = ZYX[0] * 10
		yat = ZYX[1] * 10
		xat = ZYX[2] * 10

		xmol, ymol, zmol = ut.molecules(xat, yat, zat, nsite, M, com)
		xR, yR, zR = ut.centre_mass(xat, yat, zat, nsite, M)

		mass_count = np.zeros(nslice)
		atom_count = np.zeros(nslice)
		mol_count = np.zeros(nslice)
		H_count = np.zeros(nslice)

		Aslice = DIM[0] * DIM[1]
		natom = len(xat)
		nmol = len(xmol)

	       	for n in xrange(natom):	
			x = xat[n]
			y = yat[n]
			z = zat[n] - zR

			z1 = z - xi(x, y, nm, auv1, DIM)
			An1 = Aslice * slice_area(auv1, nm, z1)

			z2 = -z + xi(x, y, nm, auv2, DIM)
			An2 = Aslice * slice_area(auv2, nm, z2)

			index1_at = int((z1 + DIM[2]/2.) * nslice / (DIM[2])) % nslice
			index2_at = int((z2 + DIM[2]/2.) * nslice / (DIM[2])) % nslice

			m = n % nsite
			mass_count[index1_at] += M[m] / An1
			mass_count[index2_at] += M[m] / An2
			atom_count[index1_at] += 1 / An1
			atom_count[index2_at] += 1 / An2

			if m == 0:
				x = xmol[n/nsite]
				y = ymol[n/nsite]
				z = zmol[n/nsite] - zR
				z1 = z - xi(x, y, nm, auv1, DIM)
				An1 = Aslice * slice_area(auv1, nm, z1)
				z2 = -z + xi(x, y, nm, auv2, DIM)
				An2 = Aslice * slice_area(auv2, nm, z2)
				index1_mol = int((z1 + DIM[2]/2.) * nslice / (DIM[2])) % nslice
				index2_mol = int((z2 + DIM[2]/2.) * nslice / (DIM[2])) % nslice
				mol_count[index1_mol] += 1 / An1
				mol_count[index2_mol] += 1 / An2

			if AT[m]== 'H':
				H_count[index1_at] += 1 / An1
				H_count[index2_at] += 1 / An2

		with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_COUNT.txt'.format(root, model.lower(), csize, nslice, nm, image), 'w') as outfile:
			np.savetxt(outfile, (mass_count, atom_count, mol_count, H_count), fmt='%-12.6f')

	return mass_count, atom_count, mol_count, H_count


def curve_mesh(root, model, csize, nm, nxy, image, auv1, auv2, DIM, ow_curve):

	if not os.path.exists('{}/DATA/INTDEN/{}_{}_{}_{}_{}_CURVE.npz'.format(root, model.lower(), csize, nm, nxy, image)) and ow_curve.upper() != 'Y':
		sys.stdout.write("PROCESSING {} SURFACE CURVE MESH {}\r".format(root,  image) )
		sys.stdout.flush()

		X = np.linspace(0, DIM[0], nxy)
		Y = np.linspace(0, DIM[1], nxy)

		XI1 = np.zeros((nxy, nxy))
		XI2 = np.zeros((nxy, nxy))
		DX1 = np.zeros((nxy, nxy))
		DY1 = np.zeros((nxy, nxy))
		DX2 = np.zeros((nxy, nxy))
		DY2 = np.zeros((nxy, nxy))
		DDX1 = np.zeros((nxy, nxy))
		DDY1 = np.zeros((nxy, nxy))
		DDX2 = np.zeros((nxy, nxy))
		DDY2 = np.zeros((nxy, nxy))
		DXDY1 = np.zeros((nxy, nxy))
		DXDY2 = np.zeros((nxy, nxy))

		for j in xrange(nxy):
			x = X[j]
			for k in xrange(nxy):
				y = Y[k]
				for u in xrange(-nm,nm+1):
					for v in xrange(-nm, nm+1):
						l = (2 * nm + 1) * (u + nm) + (v + nm)
						XI1[j][k] += function(x, u, DIM[0]) * function(y, v, DIM[1]) * auv1[l]
						XI2[j][k] += function(x, u, DIM[0]) * function(y, v, DIM[1]) * auv2[l]

						DX1[j][k] += dfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv1[l]
						DY1[j][k] += function(x, u, DIM[0]) * dfunction(y, v, DIM[1]) * auv1[l]
						DX2[j][k] += dfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv2[l]
						DY2[j][k] += function(x, u, DIM[0]) * dfunction(y, v, DIM[1]) * auv2[l]

						DDX1[j][k] += ddfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv1[l]
						DDY1[j][k] += function(x, u, DIM[0]) * ddfunction(y, v, DIM[1]) * auv1[l]
						DDX2[j][k] += ddfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv2[l]
						DDY2[j][k] += function(x, u, DIM[0]) * ddfunction(y, v, DIM[1]) * auv2[l]

						DXDY1[j][k] += dfunction(x, u, DIM[0]) * dfunction(y, v, DIM[1]) * auv1[l]
						DXDY2[j][k] += dfunction(x, u, DIM[0]) * dfunction(y, v, DIM[1]) * auv2[l]

		with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_CURVE.npz'.format(root, model.lower(), csize, nm, nxy, image), 'w') as outfile:
			np.savez(outfile, XI1=XI1, XI2=XI2, DX1=DX1, DY1=DY1, DX2=DX2, DY2=DY2, DDX1=DDX1, DDY1=DDY1, DDX2=DDX2, DDY2=DDY2, DXDY1=DXDY1, DXDY2=DXDY2)


def effective_density(root, model, csize, nslice, ntraj, suffix, DIM, nm, nxy, av_mol_den):

	print "\nBUILDING SLAB DENSITY PLOT"

	X = np.linspace(0, DIM[0], nxy)
	Y = np.linspace(0, DIM[1], nxy)
	Z = np.linspace(-1/2.*DIM[2], 1/2.*DIM[2], nslice)

	w_den_1 = np.zeros(nslice)
	w_den_2 = np.zeros(nslice)

	for image in xrange(ntraj):
		sys.stdout.write("PROCESSING {} out of {} IMAGES\r".format(image+1, ntraj) )
		sys.stdout.flush()

		if os.path.exists('{}/DATA/INTDEN/{}_{}_{}_{}_{}_WDEN.txt'.format(root, model.lower(), csize, nslice, nm, image)):
			with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_WDEN.txt'.format(root, model.lower(), csize, nslice, nm, image), 'r') as infile:
				w_den_1_temp, w_den_2_temp = np.loadtxt(infile)
		else:
			w_den_1_temp = np.zeros(nslice)
			w_den_2_temp = np.zeros(nslice)
		
			with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_CURVE.npz'.format(root, model.lower(), csize, nm, nxy, image), 'r') as infile:
				npzfile = np.load(infile)
				XI1 = npzfile['XI1']
				XI2 = npzfile['XI2']

			for n in xrange(nslice):
				for j in xrange(nxy):
					for k in xrange(nxy):
						dz = Z[n] - XI1[j][k]
						m = int((dz+DIM[2]/2.) * nslice / DIM[2]) % nslice
						w_den_1_temp[n] += av_mol_den[m] / (nxy**2)

						dz = XI2[j][k] - Z[n]
						m = int((dz+DIM[2]/2.) * nslice / DIM[2]) % nslice
						w_den_2_temp[n] += av_mol_den[m] / (nxy**2)
			
			with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_WDEN.txt'.format(root, model.lower(), csize , nslice, nm, image), 'w') as outfile:
				np.savetxt(outfile, (w_den_1_temp, w_den_2_temp))
	
		w_den_1 += w_den_1_temp / ntraj
		w_den_2 += w_den_2_temp / ntraj

	return w_den_1, w_den_2


def intrinsic_profile(traj, root, csize, suffix, AT, DIM, M, ntraj, model, nsite, natom, nmol, sigma, nslice, ncube, nm, nxy, vlim, ow_coeff, ow_count, ow_curve):

	if model.upper() == 'METHANOL': com = 'COM'
	else: com = '0'

	dz = DIM[2] / nslice
	Aslice = DIM[0]*DIM[1]
	Vslice = DIM[0]*DIM[1]*dz
	Acm = 1E-8

	av_mass_den = np.zeros(nslice)
	av_atom_den = np.zeros(nslice)
	av_mol_den = np.zeros(nslice)
	av_H_den = np.zeros(nslice)

	start_image_count = 0
	start_image_curve = 0

	for image in xrange(ntraj):

		auv1, auv2, piv_n1, piv_n2 = intrinsic_surface(traj, root, model, csize, suffix, nsite, ncube, DIM, vlim, sigma, M, nm, image, ntraj, com, ow_coeff)
		curve_mesh(root, model, csize, nm, nxy, image, auv1, auv2, DIM, ow_curve)
		mass_count, atom_count, mol_count, H_count = intrinsic_density(traj, root, model, csize, suffix, nm, image, nslice, nsite, AT, DIM, M, nxy, auv1, auv2, com, ow_count)						  
		av_mass_den += mass_count / (2 * dz * ntraj * con.N_A * Acm**3)
		av_atom_den += atom_count / (2 * dz * ntraj)
		av_mol_den += mol_count / (2 * dz * ntraj)
		av_H_den += H_count / (2 * dz * ntraj)

	w_den_1, w_den_2 = effective_density(root, model, csize, nslice, ntraj, suffix, DIM, nm, nxy, av_mol_den)

	print '\n'
	print "WRITING TO FILE..."

	with file('{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt'.format(root, model.lower(), csize, nslice, nm, ntraj), 'w') as outfile:
		np.savetxt(outfile, (av_mass_den, av_atom_den, av_mol_den, av_H_den, w_den_1, w_den_2), fmt='%-12.6f')

	print "{} {} {} COMPLETE\n".format(root, model.upper(), csize)


def main(root, model, nsite, AT, Q, M, LJ, T, cutoff, csize, TYPE, folder, nfolder, suffix, ntraj):

	for i in xrange(nfolder):
		directory = '{}/{}_{}'.format(root, TYPE.upper(), i)
		if not os.path.exists('{}/{}/{}_{}_{}_{}.nc'.format(directory, folder.upper(), model.lower(), csize, suffix, 800)): 
			ut.make_nc(directory, folder.upper(),  model.lower(), csize, suffix, ntraj, 'N')
		traj = ut.load_nc(directory, folder.upper())							
		directory = '{}/{}'.format(directory, folder.upper())

		natom = traj.n_atoms
		nmol = traj.n_residues
		DIM = np.array(traj.unitcell_lengths[0]) * 10
		sigma = np.max(LJ[1])
		lslice = 0.05 * sigma
		nslice = int(DIM[2] / lslice)
		vlim = 3
		ncube = 3
		nm = int(DIM[0] / sigma)
		nxy = 30

		if not os.path.exists("{}/DATA/ACOEFF".format(directory)): os.mkdir("{}/DATA/ACOEFF".format(directory))
		if not os.path.exists("{}/DATA/INTDEN".format(directory)): os.mkdir("{}/DATA/INTDEN".format(directory))

		if os.path.exists('{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, nm, ntraj)):
			print "FILE FOUND '{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt".format(directory, model.lower(), csize, nslice, nm, ntraj)
			overwrite = raw_input("OVERWRITE? (Y/N): ")
			if overwrite.upper() == 'Y': 
				ow_coeff = raw_input("OVERWRITE ACOEFF? (Y/N): ")
				ow_curve = raw_input("OVERWRITE CURVE? (Y/N): ")
				ow_count = raw_input("OVERWRITE COUNT? (Y/N): ")
				intrinsic_profile(traj, directory, csize, suffix, AT, DIM, M, ntraj, model, nsite, natom, nmol, sigma, nslice, ncube, nm, nxy, vlim, ow_coeff, ow_count, ow_curve)
		else: intrinsic_profile(traj, directory, csize, suffix, AT, DIM, M, ntraj, model, nsite, natom, nmol, sigma, nslice, ncube, nm, nxy, vlim, 'N','N', 'N')

