"""
*************** INTRINSIC SAMPLING METHOD MODULE *******************

Defines coefficients for a fouier series that represents
the periodic surfaces in the xy plane of an air-liquid 
interface. 	

********************************************************************
Created 24/11/16 by Frank Longford

Last modified 22/08/17 by Frank Longford
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

sqrt_2 = np.sqrt(2.)

def intrinsic_surface(directory, model, csize, nsite, nmol, ncube, DIM, COM, nm, n0, phi, psi, vlim, mol_sigma, M, frame, nframe, ow_auv, ow_recon):
	"Creates intrinsic surface of frame." 

	max_r = 1.5 * mol_sigma
	tau = 0.5 * mol_sigma

	file_name = '{}_{}_{}_{}_{}'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)
	file_name_recon = '{}_{}_{}_{}_{}_R'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)

	if not os.path.exists("{}/ACOEFF".format(directory)): os.mkdir("{}/ACOEFF".format(directory))
	if not os.path.exists("{}/INTPOS".format(directory)): os.mkdir("{}/INTPOS".format(directory))

	if os.path.exists('{}/ACOEFF/{}_INTCOEFF.txt'.format(directory, file_name)): ut.convert_txt_npy('{}/ACOEFF/{}_INTCOEFF'.format(directory, file_name))
	if os.path.exists('{}/ACOEFF/{}_INTCOEFF.txt'.format(directory, file_name_recon)): ut.convert_txt_npy('{}/ACOEFF/{}_INTCOEFF'.format(directory, file_name_recon))
	if os.path.exists('{}/ACOEFF/{}_PIVOTS.txt'.format(directory, file_name)): ut.convert_txt_npy('{}/ACOEFF/{}_PIVOTS'.format(directory, file_name))

	if not os.path.exists('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name)) or ow_auv:

		sys.stdout.write("PROCESSING {} INTRINSIC SURFACE {}\n".format(directory, frame) )
		sys.stdout.flush()

		xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)

		auv1, auv2, piv_n1, piv_n2 = build_surface(xmol, ymol, zmol-COM[frame][2], DIM, nmol, ncube, mol_sigma, nm, n0, phi, vlim, tau, max_r)

		with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name), 'w') as outfile:
			np.save(outfile, (auv1, auv2))
		with file('{}/ACOEFF/{}_PIVOTS.npy'.format(directory, file_name), 'w') as outfile:
			np.save(outfile, (piv_n1, piv_n2))

		intrinsic_positions_dxdyz(directory, model, csize, frame, auv1, auv2, nsite, nm, nm, n0, phi, psi, DIM, False, ow_auv)

		sys.stdout.write("PROCESSING {}\nINTRINSIC SURFACE RECONSTRUCTION {}\n".format(directory, frame) )
		sys.stdout.flush()

		auv1_recon, auv2_recon = surface_reconstruction(xmol, ymol, zmol-COM[frame][2], nm, n0, phi, psi, auv1, auv2, piv_n1, piv_n2, DIM)

		with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_recon), 'w') as outfile:
			np.save(outfile, (auv1_recon, auv2_recon))
		
		intrinsic_positions_dxdyz(directory, model, csize, frame, auv1_recon, auv2_recon, nsite, nm, nm, n0, phi, psi, DIM, True, ow_auv)

	elif not os.path.exists('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_recon)) or ow_recon:

		sys.stdout.write("PROCESSING {}\nINTRINSIC SURFACE RECONSTRUCTION {}\n".format(directory, frame) )
		sys.stdout.flush()

		xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)

		with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name), 'r') as infile: 
			auv1, auv2 = np.load(infile)
		with file('{}/ACOEFF/{}_PIVOTS.npy'.format(directory, file_name), 'r') as infile:
			piv_n1, piv_n2 = np.load(infile)

		auv1_recon, auv2_recon = surface_reconstruction(xmol, ymol, zmol-COM[frame][2], nm, n0, phi, psi, auv1, auv2, piv_n1, piv_n2, DIM)

		with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_recon), 'w') as outfile:
			np.save(outfile, (auv1_recon, auv2_recon))
		
		intrinsic_positions_dxdyz(directory, model, csize, frame, auv1_recon, auv2_recon, nsite, nm, nm, n0, phi, psi, DIM, True, ow_recon)

	else: 

		with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name), 'r') as infile: 
			auv1, auv2 = np.load(infile)
	   	with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_recon), 'r') as infile: 
			auv1_recon, auv2_recon = np.load(infile)
		with file('{}/ACOEFF/{}_PIVOTS.npy'.format(directory, file_name), 'r') as infile:
			piv_n1, piv_n2 = np.load(infile)


	return auv1, auv2, auv1_recon, auv2_recon, piv_n1, piv_n2


def build_surface(xmol, ymol, zmol, DIM, nmol, ncube, mol_sigma, nm, n0, phi, vlim, tau, max_r):
	"Create coefficients auv1 and aiv2 for Fourier sum representing intrinsic surface"

	print "\n ------------- BUILDING INTRINSIC SURFACE --------------"

	"""
	xmol, ymol, zmol = x, y, z positions of molecules
	mol_list = index list of molecules eligible to be used as 'pivots' for the fitting routine  
	piv_n = index of pivot molecules
	piv_z = z position of pivot molecules
	new_pivots = list of pivots to be added to piv_n and piv_z
	"""
	tau1 = tau
	tau2 = tau
	mol_list = range(nmol)
	piv_n1 = range(ncube**2)
	piv_z1 = np.zeros(ncube**2)
	piv_n2 = range(ncube**2)
	piv_z2 = np.zeros(ncube**2)
	new_piv1 = []
	new_piv2 = []

	start = time.time()

	"Remove molecules from vapour phase ans assign an initial grid of pivots furthest away from centre of mass"
	print 'Lx = {:5.3f}   Ly = {:5.3f}   nm = {:5d}\nphi = {}   n_piv = {:5d}   vlim = {:5d}   max_r = {:5.3f}'.format(DIM[0], DIM[1], nm, phi, n0, vlim, max_r) 
	print 'Selecting initial {} pivots'.format(ncube**2)
	for n in xrange(nmol):
		vapour = 0
		for m in xrange(nmol):
			dr2 = (xmol[n] - xmol[m])**2 + (ymol[n] - ymol[m])**2 + (zmol[n] - zmol[m])**2			
			if n!= m and dr2 < max_r**2: vapour += 1
			if vapour > vlim:

				indexx = int(xmol[n] * ncube / DIM[0]) % ncube
                                indexy = int(ymol[n] * ncube / DIM[1]) % ncube

				if zmol[n] < piv_z1[ncube*indexx + indexy]:
					piv_n1[ncube*indexx + indexy] = n
					piv_z1[ncube*indexx + indexy] = zmol[n]

				elif zmol[n] > piv_z2[ncube*indexx + indexy]:
					piv_n2[ncube*indexx + indexy] = n
					piv_z2[ncube*indexx + indexy] = zmol[n]

				break
		if vapour <= vlim: mol_list.remove(n)

	"Update molecular and pivot lists"
	
	for n in piv_n1: 
		mol_list.remove(n)
		new_piv1.append(n)
	for n in piv_n2:
		mol_list.remove(n)
		new_piv2.append(n)

	mol_list1 = []
	mol_list2 = []
	for n in mol_list:
		if zmol[n] < 0 : mol_list1.append(n)
		else: mol_list2.append(n)

	n_waves = 2*nm+1

	print 'Initial {} pivots selected: {:10.3f} s'.format(ncube**2, time.time() - start)

	"Form the diagonal xi^2 terms"
	diag = np.zeros(n_waves**2)
	
	for j in xrange(n_waves**2): 
		u = int(j/n_waves)-nm
		v = int(j%n_waves)-nm
		diag[j] += ut.check_uv(u, v) * (u**2 * DIM[1] / DIM[0] + v**2 * DIM[0] / DIM[1])
	diag = np.diagflat(diag)

	diag *= 4 * np.pi**2 * phi
              
	"Create A matrix and b vector for linear algebra equation Ax = b"
	A = np.zeros((2, n_waves**2, n_waves**2))
	b = np.zeros((2, n_waves**2))

	print "{:^77s} | {:^43s} | {:^21s} | {:^21s}".format('TIMINGS (s)', 'PIVOTS', 'TAU', 'INT AREA')
	print ' {:20s}  {:20s}  {:20s}  {:10s} | {:10s} {:10s} {:10s} {:10s} | {:10s} {:10s} | {:10s} {:10s}'.format('Matrix Formation', 'LU Decomposition', 'Pivot selection', 'TOTAL', 'n_piv1', '(new)', 'n_piv2', '(new)', 'surf1', 'surf2', 'surf1', 'surf2')
	print "_" * 170

	building_surface = True
	build_surf1 = True
	build_surf2 = True

	while building_surface:

		start1 = time.time()

		"Update A matrix and b vector"
		temp_A, temp_b = update_A_b(xmol, ymol, zmol, nm, n_waves, new_piv1, new_piv2, DIM)
		A += temp_A
		b += temp_b

		end1 = time.time()

		"Perform LU decomosition to solve Ax = b"
		if len(new_piv1) != 0: auv1 = LU_decomposition(A[0] + diag, b[0])
		if len(new_piv2) != 0: auv2 = LU_decomposition(A[1] + diag, b[1])

		end2 = time.time()

		if len(piv_n1) == n0: 
			build_surf1 = False
			new_piv1 = []
		if len(piv_n2) == n0: 
			build_surf2 = False
			new_piv2 = []

		if build_surf1: zeta_list1 = zeta_list(xmol, ymol, mol_list1, auv1, nm, DIM)
		if build_surf2: zeta_list2 = zeta_list(xmol, ymol, mol_list2, auv2, nm, DIM)

		if build_surf1 or build_surf2:
			finding_pivots = True
			piv_search1 = True
			piv_search2 = True
		else:
			finding_pivots = False
			building_surface = False
			print "ENDING SEARCH"

                while finding_pivots:

			if piv_search1 and build_surf1: mol_list1, new_piv1, piv_n1 = pivot_selection(zmol, mol_sigma, n0, mol_list1, zeta_list1, piv_n1, tau1)
			if piv_search2 and build_surf2: mol_list2, new_piv2, piv_n2 = pivot_selection(zmol, mol_sigma, n0, mol_list2, zeta_list2, piv_n2, tau2)

                        if len(new_piv1) == 0 and len(piv_n1) < n0: tau1 += 0.1 * tau 
			else: piv_search1 = False

                        if len(new_piv2) == 0 and len(piv_n2) < n0: tau2 += 0.1 * tau 
			else: piv_search2 = False

			if piv_search1 or piv_search2: finding_pivots = True
                        else: finding_pivots = False

		end = time.time()
	
		area1 = slice_area(auv1**2, nm, nm, DIM)
		area2 = slice_area(auv2**2, nm, nm, DIM)

		print ' {:20.3f}  {:20.3f}  {:20.3f}  {:10.3f} | {:10d} {:10d} {:10d} {:10d} | {:10.3f} {:10.3f} | {:10.3f} {:10.3f}'.format(end1 - start1, end2 - end1, end - end2, end - start1, len(piv_n1), len(new_piv1), len(piv_n2), len(new_piv2), tau1, tau2, area1, area2)			

	print '\nTOTAL time: {:7.2f} s \n'.format(end - start)

	return auv1, auv2, piv_n1, piv_n2


def zeta_list(xmol, ymol, mol_list, auv, nm, DIM):

	zeta_list = np.zeros(len(xmol))
	for n in mol_list:
                x = xmol[n]
                y = ymol[n]
                zeta = xi(x, y, nm, nm, auv, DIM)
		zeta_list[n] += zeta
               
	return zeta_list


def pivot_selection(zmol, mol_sigma, n0, mol_list, zeta_list, piv_n, tau):

	new_piv = []
	dz_new_piv = []
	for n in mol_list:
		z = zmol[n]
                zeta = zeta_list[n]
                if abs(zeta - z) <= tau:
                        new_piv.append(n)
			dz_new_piv.append(abs(zeta - z))
                elif abs(zeta - z) > 3.0 * mol_sigma:
                        mol_list.remove(n)

	ut.bubblesort(new_piv, dz_new_piv)

	for i, n in enumerate(new_piv):
		piv_n.append(n)
                try: mol_list.remove(n)
		except: print n, mol_list, piv_n[i]
                if len(piv_n) == n0: 
			new_piv = new_piv[:i] 
			break

	return mol_list, new_piv, piv_n


def LU_decomposition(A, b):
	lu, piv  = sp.linalg.lu_factor(A)
	auv = sp.linalg.lu_solve((lu, piv), b)
	return auv


def update_A_b(xmol, ymol, zmol, nm, n_waves, new_piv1, new_piv2, DIM):

	A = np.zeros((2, n_waves**2, n_waves**2))
	b = np.zeros((2, n_waves**2))

	fuv1 = np.array([[function(xmol[ns], int(j/n_waves)-nm, DIM[0]) * function(ymol[ns], int(j%n_waves)-nm, DIM[1]) for ns in new_piv1] for j in xrange(n_waves**2)])
        b[0] += np.array([np.sum([(zmol[new_piv1[ns]]) * fuv1[k][ns] for ns in xrange(len(new_piv1))]) for k in xrange(n_waves**2)])
        
	fuv2 = np.array([[function(xmol[ns], int(j/n_waves)-nm, DIM[0]) * function(ymol[ns], int(j%n_waves)-nm, DIM[1]) for ns in new_piv2] for j in xrange(n_waves**2)])
	b[1] += np.array([np.sum([(zmol[new_piv2[ns]]) * fuv2[k][ns] for ns in xrange(len(new_piv2))]) for k in xrange(n_waves**2)])

	A[0] += np.dot(fuv1, np.transpose(fuv1))
	A[1] += np.dot(fuv2, np.transpose(fuv2))

	return A, b


def surface_reconstruction(xmol, ymol, zmol, nm, n0, phi, psi, auv1, auv2, piv_n1, piv_n2, DIM):

	var_lim = 1E-3
	n_waves = 2*nm + 1

	print "PERFORMING SURFACE RESTRUCTURING"
	print 'Lx = {:5.3f}   Ly = {:5.3f}   nm = {:5d}\nphi = {}  psi = {}  n_piv = {:5d}  var_lim = {}'.format(DIM[0], DIM[1], nm, phi, psi, n0, var_lim) 
	print 'Setting up wave product and coefficient matricies'

	orig_psi1 = psi
	orig_psi2 = psi
	psi1 = psi
	psi2 = psi

	start = time.time()	

	"Form the diagonal xi^2 terms"
	
	fuv1 = np.array([[function(xmol[ns], int(j/n_waves)-nm, DIM[0]) * function(ymol[ns], int(j%n_waves)-nm, DIM[1]) for ns in piv_n1] for j in xrange(n_waves**2)])
        b1 = np.array([np.sum([(zmol[piv_n1[ns]]) * fuv1[k][ns] for ns in xrange(len(piv_n1))]) for k in xrange(n_waves**2)])
        
	fuv2 = np.array([[function(xmol[ns], int(j/n_waves)-nm, DIM[0]) * function(ymol[ns], int(j%n_waves)-nm, DIM[1]) for ns in piv_n2] for j in xrange(n_waves**2)])
	b2 = np.array([np.sum([(zmol[piv_n2[ns]]) * fuv2[k][ns] for ns in xrange(len(piv_n2))]) for k in xrange(n_waves**2)])

	diag = np.zeros(n_waves**2)
	coeff = np.zeros((n_waves**2, n_waves**2))

	for j in xrange(n_waves**2):
		u1 = int(j/n_waves)-nm
		v1 = int(j%n_waves)-nm
		diag[j] += ut.check_uv(u1, v1) * (phi * (u1**2 * DIM[1] / DIM[0] + v1**2 * DIM[0] / DIM[1]))
		for k in xrange(j+1):
			u2 = int(k/n_waves)-nm
			v2 = int(k%n_waves)-nm
			coeff[j][k] += 16 * np.pi**4 * (u1**2 * u2**2 / DIM[0]**4 + v1**2 * v2**2 / DIM[1]**4 + (u1**2 * v2**2 + u2**2 * v1**2) / (DIM[0]**2 * DIM[1]**2))
			coeff[k][j] = coeff[j][k]

	diag = 4 * np.pi**2 * np.diagflat(diag) 
	ffuv1 = np.dot(fuv1, np.transpose(fuv1))
	ffuv2 = np.dot(fuv2, np.transpose(fuv2))

	end_setup1 = time.time()

	print "{:^74s} | {:^21s} | {:^43s}".format('TIMINGS (s)', 'PSI', 'VAR(H)' )
	print ' {:20s} {:20s} {:20s} {:10s} | {:10s} {:10s} | {:10s} {:10s} {:10s} {:10s}'.format('Matrix Formation', 'LU Decomposition', 'Var Estimation', 'TOTAL', 'surf1', 'surf2', 'surf1', 'piv1', 'surf2', 'piv2')
	print "_" * 165

	H_var1 = ut.H_var_est(auv1**2, nm, nm, DIM)
	H_var2 = ut.H_var_est(auv2**2, nm, nm, DIM)

	auv1_matrix = np.tile(auv1, (n_waves**2, 1))
	H_piv_var1 = np.sum(auv1_matrix * np.transpose(auv1_matrix) * ffuv1 * coeff / n0)
	auv2_matrix = np.tile(auv2, (n_waves**2, 1))
	H_piv_var2 = np.sum(auv2_matrix * np.transpose(auv2_matrix) * ffuv2 * coeff / n0)

	end_setup2 = time.time()
	
	print ' {:20.3f} {:20.3f} {:20.3f} {:10.3f} | {:10.6f} {:10.6f} | {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format( end_setup1-start, 0, end_setup2-end_setup1, end_setup2-start, 0, 0, H_var1, H_piv_var1, H_var2, H_piv_var2)

	reconstructing = True
	recon_1 = True
	recon_2 = True
	loop1 = 0
	loop2 = 0

	while reconstructing:

		start1 = time.time()
        
		"Update A matrix and b vector"
		A1 = ffuv1 * (1. + coeff * psi1 / n0)
		A2 = ffuv2 * (1. + coeff * psi2 / n0) 

		end1 = time.time()

		"Perform LU decomosition to solve Ax = b"
		if recon_1: auv1_recon = LU_decomposition(A1 + diag, b1)
		if recon_2: auv2_recon = LU_decomposition(A2 + diag, b2)

		end2 = time.time()

		H_var1_recon = ut.H_var_est(auv1_recon**2, nm, nm, DIM)
		H_var2_recon = ut.H_var_est(auv2_recon**2, nm, nm, DIM)

		if recon_1:
			auv1_matrix = np.tile(auv1_recon, (n_waves**2, 1))
			H_piv_var1_recon = np.sum(auv1_matrix * np.transpose(auv1_matrix) * ffuv1 * coeff / n0)
		if recon_2:
			auv2_matrix = np.tile(auv2_recon, (n_waves**2, 1))
			H_piv_var2_recon = np.sum(auv2_matrix * np.transpose(auv2_matrix) * ffuv2 * coeff / n0)

		end3 = time.time()

		print ' {:20.3f} {:20.3f} {:20.3f} {:10.3f} | {:10.6f} {:10.6f} | {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(end1 - start1, end2 - end1, end3 - end2, end3 - start1, psi1, psi2, H_var1_recon, H_piv_var1_recon, H_var2_recon, H_piv_var2_recon)

		if abs(H_piv_var1_recon - H_var1_recon) <= var_lim: recon_1 = False
		else: 
			psi1 += orig_psi1 * (H_piv_var1_recon - H_var1_recon)
			if abs(H_var1_recon) > 5 * H_var1 or loop1 > 40:
				orig_psi1 *= 0.5 
				psi1 = orig_psi1
				loop1 = 0
			else: loop1 += 1
		if abs(H_piv_var2_recon - H_var2_recon) <= var_lim: recon_2 = False
		else: 
			psi2 += orig_psi2 * (H_piv_var2_recon - H_var2_recon)
			if abs(H_var2_recon) > 5 * H_var2 or loop2 > 40: 
				orig_psi2 *= 0.5 
				psi2 = orig_psi2
				loop2 = 0
			else: loop2 += 1

		if not recon_1 and not recon_2: reconstructing = False

	end = time.time()

	print '\nTOTAL time: {:7.2f} s \n'.format(end - start)

	return auv1_recon, auv2_recon


def function(x, u, Lx):

	if u >= 0: return np.cos(2 * np.pi * u * x / Lx)
	else: return np.sin(2 * np.pi * abs(u) * x / Lx)


def dfunction(x, u, Lx):

	if u >= 0: return - 2 * np.pi * u  / Lx * np.sin(2 * np.pi * u * x  / Lx)
	else: return 2 * np.pi * abs(u) / Lx * np.cos(2 * np.pi * abs(u) * x / Lx)


def ddfunction(x, u, Lx):

	return - 4 * np.pi**2 * u**2 / Lx**2 * function(x, u, Lx)


def xi(x, y, nm, qm, auv, DIM):

	zeta = 0
	for u in xrange(-qm, qm+1):
		for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			zeta += function(x, u, DIM[0]) * function(y, v, DIM[1]) * auv[j]
	return zeta


def dxyi(x, y, nm, qm, auv, DIM):

	dzx = 0
	dzy = 0
	for u in xrange(-qm, qm+1):
		for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			dzx += dfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv[j]
			dzy += function(x, u, DIM[0]) * dfunction(y, v, DIM[1]) * auv[j]
	return dzx, dzy


def ddxyi(x, y, nm, qm, auv, DIM):


	ddzx = 0
	ddzy = 0
	for u in xrange(-qm, qm+1):
		for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			ddzx += ddfunction(x, u, DIM[0]) * function(y, v, DIM[1]) * auv[j]
			ddzy += function(x, u, DIM[0]) * ddfunction(y, v, DIM[1]) * auv[j]
	return ddzx, ddzy


def mean_curve_est(x, y, nm, qm, auv, DIM):

	H = 0
	for u in xrange(-qm, qm+1):
		for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			H += -4 * np.pi**2 * (u**2 / DIM[0]**2 + v**2 / DIM[1]**2) * function(x, u, DIM[0]) * function(y, v, DIM[1]) * auv[j]
	return H


def optimise_ns(directory, model, csize, nmol, nsite, nm, phi, vlim, ncube, DIM, COM, M, mol_sigma, start_ns, end_ns):

	if not os.path.exists('{}/ACOEFF'.format(directory)): os.mkdir('{}/DATA/ACOEFF'.format(directory))

	mol_ex_1 = []
	mol_ex_2 = []

	nframe = 20

	NS = np.arange(start_ns, end_ns, 0.05)
	
	print NS

	for ns in NS:

		n0 = int(DIM[0] * DIM[1] * ns / mol_sigma**2)

		tot_piv_n1 = np.zeros((nframe, n0))
		tot_piv_n2 = np.zeros((nframe, n0))

		for frame in xrange(nframe):
			xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)
			xR, yR, zR = COM[frame]
			auv1, auv2, piv_n1, piv_n2 = intrinsic_surface(directory, model, csize, nsite, nmol, ncube, DIM, COM, nm, n0, phi, vlim, mol_sigma, M, frame, nframe,False, True)

			tot_piv_n1[frame] += piv_n1
			tot_piv_n2[frame] += piv_n2 

		ex_1, ex_2 = mol_exchange(tot_piv_n1, tot_piv_n2, nframe, n0)

		mol_ex_1.append(ex_1)
		mol_ex_2.append(ex_2)

		print ns, n0, ex_1, ex_2

	print NS[np.argmin((np.array(mol_ex_1) + np.array(mol_ex_2)) / 2.)], np.min((np.array(mol_ex_1) + np.array(mol_ex_2)) / 2.)

	#"""
	plt.scatter(NS, (np.array(mol_ex_1) + np.array(mol_ex_2)) / 2.)
	plt.scatter(NS, mol_ex_1, c='g')
	plt.scatter(NS, mol_ex_2, c='r')
	plt.axis([np.min(NS), np.max(NS), 0, np.max(mol_ex_1)])
	plt.show()
	#"""

	return NS[np.argmin((np.array(mol_ex_1) + np.array(mol_ex_2)) / 2.)]


def mol_exchange(piv_1, piv_2, nframe, n0):

	n_1 = 0
	n_2 = 0

	for frame in xrange(nframe-1):

		n_1 += len(set(piv_1[frame]) - set(piv_1[frame+1]))
		n_2 += len(set(piv_2[frame]) - set(piv_2[frame+1]))

	return n_1 / (n0 * float(nframe-1) * 1000), n_2 / (n0 * float(nframe-1) * 1000)


def area_correction(z, auv_2, nm, qm, DIM):

        Axi = 0

        for u in xrange(-qm, qm+1):
                for v in xrange(-qm, qm+1):
                        j = (2 * nm + 1) * (u + nm) + (v + nm)
                        dot_prod = 4 * np.pi**2  * (u**2/DIM[0]**2 + v**2/DIM[1]**2)

			if dot_prod != 0:
                        	f_2 = ut.check_uv(u, v) * auv_2[j] / 4.
                        	Axi += f_2 * dot_prod / (1 + np.sqrt(f_2) * abs(z) * dot_prod)**2 

        return 1 + 0.5*Axi



def slice_area(auv_2, nm, qm, DIM):
	"Obtain the intrinsic surface area"

        Axi = 0.0

	for u in xrange(-qm, qm+1):
                for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			dot_prod = np.pi**2  * (u**2/DIM[0]**2 + v**2/DIM[1]**2)

			if dot_prod != 0:
				f_2 = ut.check_uv(u, v) * auv_2[j]
				Axi += f_2 * dot_prod

        return 1 + 0.5*Axi


def auv_qm(auv, nm, qm):

	auv_qm = np.zeros((2*qm+1)**2)

	for u in xrange(-qm, qm+1):
                for v in xrange(-qm, qm+1):
			j1 = (2 * nm + 1) * (u + nm) + (v + nm)
			j2 = (2 * qm + 1) * (u + qm) + (v + qm)

			auv_qm[j2] = auv[j1] 
	return auv_qm

def auv2_to_f2(auv2, nm):

	f2 = np.zeros((2*nm+1)**2)

	for u in xrange(-nm, nm+1):
                for v in xrange(-nm, nm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm) 
			f2[j] = auv2[j] * ut.check_uv(u, v) / 4.
	return f2


def auv_xy_correlation(auv_2, nm, qm):

	auv_2[len(auv_2)/2] = 0
	f2 = auv2_to_f2(auv_2, nm)
	
	f2_qm = auv_qm(f2, nm, qm).reshape(((2*qm+1), (2*qm+1)))
	xy_corr = np.fft.fftshift(np.fft.ifftn(f2_qm))
	#xy_corr = np.fft.ifftn(f2_qm)

	return np.abs(xy_corr) * (2*qm+1)**2 / np.sum(f2_qm)


def auv_correlation(auv_t, nm):

      	tot_Gamma = np.zeros((2*nm+1)**2)
	tot_omega = np.zeros((2*nm+1)**2)

	l = len(tot_Gamma)/4
	dtau = 1

        for u in xrange(-nm, nm+1):
                for v in xrange(-nm, nm+1):
                        j = (2 * nm + 1) * (u + nm) + (v + nm)

			ACF_auv = ut.autocorr(auv_t[j]) #* np.mean(auv_t[j]**2)

			try:
				opt, ocov = curve_fit(hydro_func, np.arange(l)*dtau, ACF_auv[:l])

				#print u, v, opt
				"""
				if abs(u) < 5 and abs(v) < 5:
					curve = [hydro_func(t, tot_Gamma[j-1], tot_Gamma[j-1]) for t in np.linspace(0, l*dtau, l*10)]
					plt.figure(0)
					plt.title('{} {}'.format(u, v))
					plt.plot(np.arange(len(auv_t[j])) * dtau, auv_t[j])
					plt.figure(1)
					plt.title('{} {}'.format(u, v))
					plt.plot(np.arange(l)*dtau, ACF_auv[:l])
					plt.plot(np.linspace(0, l*dtau, l*10), curve)
					plt.show()
				#"""			

				tot_Gamma[j] = opt[0]
				tot_omega[j] = opt[1]

			except:

				tot_Gamma[j] = np.nan
				tot_omega[j] = np.nan

				"""
				print ACF_auv[0], np.mean(auv_t[j]**2), np.var(auv_t[j])
				curve = [hydro_func(t, tot_Gamma[j-1], tot_Gamma[j-1]) for t in np.linspace(0, l*5., l*100)]

				plt.figure(0)
				plt.title('{} {}'.format(u, v))
				plt.plot(np.arange(len(auv_t[j])), auv_t[j])
				plt.figure(1)
				plt.title('{} {}'.format(u, v))
				plt.plot(np.arange(l), ACF_auv[:l])
				plt.plot(np.arange(l), ut.autocorr(auv_t[j-1])[:l])
				plt.plot(np.linspace(0, l*5, l*100), curve)
				plt.show()
				"""

        return tot_Gamma, tot_omega


def hydro_func(t, Gamma, omega):

	return np.exp(-Gamma * t) * np.cos(omega * t)


def get_hydro_param(tot_Gamma, tot_omega, nm, qm, DIM, q2_set):

	Gamma_list = []
        Gamma_hist = np.zeros(len(q2_set))
	omega_list = []
        omega_hist = np.zeros(len(q2_set))

        count = np.zeros(len(q2_set))

	for u in xrange(-qm, qm+1):
                for v in xrange(-qm, qm+1):
                        j = (2 * nm + 1) * (u + nm) + (v + nm)
			set_index = np.round(u**2*DIM[1]/DIM[0] + v**2*DIM[0]/DIM[1], 4)	
	
			if set_index != 0:
                                Gamma_list.append(tot_Gamma[j])
                                Gamma_hist[q2_set == set_index] += tot_Gamma[j]
				omega_list.append(tot_omega[j])
                                omega_hist[q2_set == set_index] += tot_omega[j]

                                count[q2_set == set_index] += 1

        for i in xrange(len(q2_set)):
                if count[i] != 0: 
			Gamma_hist[i] *= 1. / count[i]
			omega_hist[i] *= 1. / count[i]
			
	return Gamma_hist, omega_hist


def gamma_q_auv(auv_2, nm, qm, DIM, T, q2_set):

	gamma_list = []
	gamma_hist = np.zeros(len(q2_set))
	gamma_count = np.zeros(len(q2_set))

	dim = np.array(DIM) * 1E-10

	coeff = con.k * 1E3 * T

	for u in xrange(-qm, qm+1):
		for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			dot_prod = np.pi**2 * (u**2 * dim[1] / dim[0] + v**2 * dim[0] / dim[1])
			set_index = np.round(u**2*dim[1]/dim[0] + v**2*dim[0]/dim[1], 4)

			if set_index != 0:
				gamma = 1. / (ut.check_uv(u, v) * auv_2[j] * 1E-20 * dot_prod)
				gamma_list.append(gamma)
				gamma_hist[q2_set == set_index] += gamma
				gamma_count[q2_set == set_index] += 1

	for i in xrange(len(q2_set)):
		if gamma_count[i] != 0: gamma_hist[i] *= 1. / gamma_count[i]

	return gamma_hist * coeff#np.array(gamma_list) * coeff#, 


def power_spec_auv(auv_2, nm, qm, DIM, q2_set):

	p_spec_list = []
	p_spec_hist = np.zeros(len(q2_set))
	p_spec_count = np.zeros(len(q2_set))

	dim = np.array(DIM) * 1E-10

	for u in xrange(-qm, qm+1):
		for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			set_index = np.round(u**2*dim[1]/dim[0] + v**2*dim[0]/dim[1], 4)

			if set_index != 0:
				p_spec = auv_2[j] * ut.check_uv(u, v) / 4.
				p_spec_list.append(p_spec)
				p_spec_hist[q2_set == set_index] += p_spec
				p_spec_count[q2_set == set_index] += 1

	for i in xrange(len(q2_set)):
		if p_spec_count[i] != 0: p_spec_hist[i] *= 1. / p_spec_count[i]

	return p_spec_hist


def gamma_q_f(f_2, nm, qm, DIM, T, q2_set):

	gamma_list = []
	gamma_hist = np.zeros(len(q2_set))
	gamma_count = np.zeros(len(q2_set))

	DIM = np.array(DIM) * 1E-10
	f_2 *= 1E-20

	coeff = con.k * 1E3 * T / (DIM[0] * DIM[1])

	for u in xrange(-qm, qm+1):
		for v in xrange(-qm, qm+1):
			j = (2 * nm + 1) * (u + nm) + (v + nm)
			dot_prod = 4 * np.pi**2 * (u**2 / DIM[0]**2 + v**2 / DIM[1]**2)
			set_index = u**2 + v**2

			if abs(u) + abs(v) == 0: pass
			else:
				if u == 0 or v == 0: gamma = 1. / (f_2[j] * dot_prod)
				else: gamma = 1. / (f_2[j] * dot_prod)
				gamma_list.append(gamma)
				gamma_hist[q2_set == set_index] += gamma
				gamma_count[q2_set == set_index] += 1

	for i in xrange(len(q2_set)):
		if gamma_count[i] != 0: gamma_hist[i] *= 1. / gamma_count[i]

	return np.array(gamma_list) * coeff, gamma_hist * coeff


def intrinsic_positions_dxdyz(directory, model, csize, frame, auv1, auv2, nsite, nm, QM, n0, phi, psi, DIM, recon, ow_all):

        xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)

	nmol = len(xmol)
	
	int_z_mol = np.zeros((2, nmol))
        dxdyz_mol = np.zeros((4, nmol)) 
	ddxddyz_mol = np.zeros((4, nmol))

	for qm in xrange(QM+1):
		sys.stdout.write("PROCESSING {} INTRINSIC POSITIONS AND DXDY {}: nm = {} qm = {}\r".format(directory, frame, nm, qm))
		sys.stdout.flush()

		if recon: file_name = '{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)
		else: file_name = '{}_{}_{}_{}_{}_{}'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)

		if os.path.exists('{}/INTPOS/{}_INTZ_AT.txt'.format(directory, file_name)): os.remove('{}/INTPOS/{}_INTZ_AT.txt'.format(directory, file_name))
		if os.path.exists('{}/INTPOS/{}_INTZ_MOL.txt'.format(directory, file_name)): ut.convert_txt_npy('{}/INTPOS/{}_INTZ_MOL'.format(directory, file_name))
		if os.path.exists('{}/INTPOS/{}_INTDXDY_MOL.txt'.format(directory, file_name)): ut.convert_txt_npy('{}/INTPOS/{}_INTDXDY_MOL'.format(directory, file_name))
		if os.path.exists('{}/INTPOS/{}_INTDDXDDY_MOL.txt'.format(directory, file_name)): ut.convert_txt_npy('{}/INTPOS/{}_INTDDXDDY_MOL'.format(directory, file_name))

		if os.path.exists('{}/INTPOS/{}_INTDDXDDY_MOL.npy'.format(directory, file_name)) and not ow_all:
			with file('{}/INTPOS/{}_INTZ_MOL.npy'.format(directory, file_name), 'r') as infile:
				int_z_mol = np.load(infile)
			with file('{}/INTPOS/{}_INTDXDY_MOL.npy'.format(directory, file_name), 'r') as infile:
				dxdyz_mol = np.load(infile)
			with file('{}/INTPOS/{}_INTDDXDDY_MOL.npy'.format(directory, file_name), 'r') as infile:
				ddxddyz_mol = np.load(infile)
		else:
			for n in xrange(nmol):
				sys.stdout.write("PROCESSING {} INTRINSIC POSITIONS AND DXDY {}: nm = {} qm = {}  {} out of {}  molecules\r".format(directory, frame, nm, qm, n, nmol))
		                sys.stdout.flush()

				if qm == 0:
					j = (2 * nm + 1) * nm + nm

					f_x = function(xmol[n], 0, DIM[0])
					f_y = function(ymol[n], 0, DIM[1])

					int_z_mol[0][n] += f_x * f_y * auv1[j]
					int_z_mol[1][n] += f_x * f_y * auv2[j]

				else:
					for u in [-qm, qm]:
						for v in xrange(-qm, qm+1):
							j = (2 * nm + 1) * (u + nm) + (v + nm)

							f_x = function(xmol[n], u, DIM[0])
							f_y = function(ymol[n], v, DIM[1])
							df_dx = dfunction(xmol[n], u, DIM[0])
							df_dy = dfunction(ymol[n], v, DIM[1])
							ddf_ddx = ddfunction(xmol[n], u, DIM[0])
							ddf_ddy = ddfunction(ymol[n], v, DIM[1])

							int_z_mol[0][n] += f_x * f_y * auv1[j]
							int_z_mol[1][n] += f_x * f_y * auv2[j]
							dxdyz_mol[0][n] += df_dx * f_y * auv1[j]
							dxdyz_mol[1][n] += f_x * df_dy * auv1[j]
							dxdyz_mol[2][n] += df_dx * f_y * auv2[j]
							dxdyz_mol[3][n] += f_x * df_dy * auv2[j]
							ddxddyz_mol[0][n] += ddf_ddx * f_y * auv1[j]
							ddxddyz_mol[1][n] += f_x * ddf_ddy * auv1[j]
							ddxddyz_mol[2][n] += ddf_ddx * f_y * auv2[j]
							ddxddyz_mol[3][n] += f_x * ddf_ddy * auv2[j]

					for u in xrange(-qm+1, qm):
						for v in [-qm, qm]:
							j = (2 * nm + 1) * (u + nm) + (v + nm)

							f_x = function(xmol[n], u, DIM[0])
							f_y = function(ymol[n], v, DIM[1])
							df_dx = dfunction(xmol[n], u, DIM[0])
							df_dy = dfunction(ymol[n], v, DIM[1])
							ddf_ddx = ddfunction(xmol[n], u, DIM[0])
							ddf_ddy = ddfunction(ymol[n], v, DIM[1])

							int_z_mol[0][n] += f_x * f_y * auv1[j]
							int_z_mol[1][n] += f_x * f_y * auv2[j]
							dxdyz_mol[0][n] += df_dx * f_y * auv1[j]
							dxdyz_mol[1][n] += f_x * df_dy * auv1[j]
							dxdyz_mol[2][n] += df_dx * f_y * auv2[j]
							dxdyz_mol[3][n] += f_x * df_dy * auv2[j]
							ddxddyz_mol[0][n] += ddf_ddx * f_y * auv1[j]
							ddxddyz_mol[1][n] += f_x * ddf_ddy * auv1[j]
							ddxddyz_mol[2][n] += ddf_ddx * f_y * auv2[j]
							ddxddyz_mol[3][n] += f_x * ddf_ddy * auv2[j]


			with file('{}/INTPOS/{}_INTZ_MOL.npy'.format(directory, file_name), 'w') as outfile:
				np.save(outfile, (int_z_mol))
			with file('{}/INTPOS/{}_INTDXDY_MOL.npy'.format(directory, file_name), 'w') as outfile:
		       		np.save(outfile, (dxdyz_mol))
			with file('{}/INTPOS/{}_INTDDXDDY_MOL.npy'.format(directory, file_name), 'w') as outfile:
		       		np.save(outfile, (ddxddyz_mol))

	return int_z_mol, dxdyz_mol, ddxddyz_mol


def intrinsic_z_den_corr(directory, COM, model, csize, nm, qm, n0, phi, psi, frame, nslice, nsite, DIM, recon, ow_count):
	"Saves atom, mol and mass intrinsic profiles of trajectory frame" 

	lslice = DIM[2] / nslice
	nz = 100
        nnz = 100

	if recon:
		file_name_count = '{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5),frame)
		file_name_norm = '{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nz, nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_pos = '{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_coeff = '{}_{}_{}_{}_{}_R'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)
	else: 
		file_name_count = '{}_{}_{}_{}_{}_{}_{}'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5), frame)	
		file_name_norm = '{}_{}_{}_{}_{}_{}_{}'.format(model.lower(), nz, nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_pos = '{}_{}_{}_{}_{}_{}'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_coeff = '{}_{}_{}_{}_{}'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)

	if os.path.exists('{}/INTDEN/{}_COUNTCORR.npy'.format(directory, file_name_count)) and not ow_count:
		try:
			with file('{}/INTDEN/{}_COUNTCORR.npy'.format(directory, file_name_count)) as infile:
				count_corr_array = np.load(infile)
		except:
			print "LOADING FAILED {}/INTDEN/{}_COUNTCORR.npy".format(directory, file_name_count) 
			ow_count = True
	else: ow_count = True

	if os.path.exists('{}/INTDEN/{}_N_NZ.npy'.format(directory, file_name_norm)) and not ow_count:
                try:
                        with file('{}/INTDEN/{}_N_NZ.npy'.format(directory, file_name_norm)) as infile:
                                z_nz_array = np.load(infile)
                except: 
			print "LOADING FAILED {}/INTDEN/{}_N_NZ.npy".format(directory, file_name_norm)
			ow_count = True
        else: ow_count = True

	if ow_count:

		xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)
		_, _, zcom = COM[frame]

		count_corr_array = np.zeros((nslice, nnz))
		z_nz_array = np.zeros((nz, nnz))	

		nmol = len(xmol)

		try:
			with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_coeff), 'r') as infile:
                                auv1, auv2 = np.load(infile)
			with file('{}/INTPOS/{}_INTZ_MOL.npy'.format(directory, file_name_pos), 'r') as infile:
				int_z_mol = np.load(infile)
			with file('{}/INTPOS/{}_INTDXDY_MOL.npy'.format(directory, file_name_pos), 'r') as infile:
                                dxdyz_mol = np.load(infile)
		except:
			with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_coeff), 'r') as infile: 
				auv1, auv2 = np.load(infile)
			int_z_mol, dxdyz_mol, ddxddyz_mol = intrinsic_positions_dxdyz(directory, model, csize, frame, auv1, auv2, nsite, nm, qm, n0, phi, psi, DIM, recon, False)

		for n in xrange(nmol):
			sys.stdout.write("PROCESSING {} INTRINSIC DENSITY {}: nm = {} qm = {}  {} out of {}  molecules\r".format(directory, frame, nm, qm, n, nmol) )
			sys.stdout.flush()

			x = xmol[n]
			y = ymol[n]
			z = zmol[n] - zcom

			int_z1 = int_z_mol[0][n]
			int_z2 = int_z_mol[1][n]

			z1 = z - int_z1
			z2 = -z + int_z2

			index1_mol = int((z1 + DIM[2]/2.) * nslice / (DIM[2])) % nslice
			index2_mol = int((z2 + DIM[2]/2.) * nslice / (DIM[2])) % nslice

			dzx1 = dxdyz_mol[0][n]
	                dzy1 = dxdyz_mol[1][n]
	                dzx2 = dxdyz_mol[2][n]
	                dzy2 = dxdyz_mol[3][n]

			normal1 = ut.unit_vector([-dzx1, -dzy1, 1])
			normal2 = ut.unit_vector([-dzx2, -dzy2, 1])

			index1_nz = int(abs(normal1[2]) * nnz) % nnz
	                index2_nz = int(abs(normal2[2]) * nnz) % nnz

			count_corr_array[index1_mol][index1_nz] += 1
	                count_corr_array[index2_mol][index2_nz] += 1

	                index1_mol = int(abs(int_z1 - auv1[len(auv1)/2]) * 2 * nz / (nz*lslice)) % nz
	                index2_mol = int(abs(int_z2 - auv2[len(auv2)/2]) * 2 * nz / (nz*lslice)) % nz

	                z_nz_array[index1_mol][index1_nz] += 1
	                z_nz_array[index2_mol][index2_nz] += 1


		with file('{}/INTDEN/{}_COUNTCORR.npy'.format(directory, file_name_count), 'w') as outfile:
			np.save(outfile, (count_corr_array))
		with file('{}/INTDEN/{}_N_NZ.npy'.format(directory, file_name_norm), 'w') as outfile:
                        np.save(outfile, (z_nz_array))

	return count_corr_array, z_nz_array



def intrinsic_R_tensors(directory, model, csize, frame, nslice, COM, DIM, nsite, nm, qm, n0, phi, psi, recon, ow_R):

	if recon:
		file_name_euler = '{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5),frame)
		file_name_pos = '{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_coeff = '{}_{}_{}_{}_{}_R'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)
	else: 
		file_name_euler = '{}_{}_{}_{}_{}_{}_{}'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5), frame)	
		file_name_pos = '{}_{}_{}_{}_{}_{}'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_coeff = '{}_{}_{}_{}_{}'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)

	if os.path.exists('{}/INTEULER/{}_ODIST.npy'.format(directory, file_name_euler)) and not ow_R:
		try:
			with file('{}/INTEULER/{}_ODIST.npy'.format(directory, file_name_euler), 'r') as infile:
				temp_int_O = np.load(infile)
		except: 
			print "LOADING FAILED {}/INTEULER/{}_ODIST.npy".format(directory, file_name_euler)
			ow_R = True
	else: ow_R = True

	if ow_R:

		xat, yat, zat = ut.read_atom_positions(directory, model, csize, frame)
		xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)
		xR, yR, zR = COM[frame]

		nmol = len(xmol)

		temp_int_O = np.zeros((nslice, 9))

		try:	
			with file('{}/INTPOS/{}_INTZ_MOL.npy'.format(directory, file_name_pos), 'r') as infile:
				int_z_mol = np.load(infile)
			with file('{}/INTPOS/{}_INTDXDY_MOL.npy'.format(directory, file_name_pos), 'r') as infile:
				dxdyz_mol = np.load(infile)
		except:
			with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_coeff), 'r') as infile: 
				auv1, auv2 = np.load(infile)
			int_z_at, int_z_mol, dxdyz_mol, ddxddyz_mol = intrinsic_positions_dxdyz(directory, model, csize, frame, auv1, auv2, nsite, nm, QM, n0, phi, psi, DIM, recon, False)

		for j in xrange(nmol):
			sys.stdout.write("PROCESSING {} ODIST {}: {} out of {}  molecules\r".format(directory, frame, j, nmol))
			sys.stdout.flush()

			molecule = np.zeros((nsite, 3))

			dzx1 = dxdyz_mol[0][j]
			dzy1 = dxdyz_mol[1][j]
			dzx2 = dxdyz_mol[2][j]
			dzy2 = dxdyz_mol[3][j]

			for l in xrange(nsite):
				molecule[l][0] = xat[j*nsite+l]
				molecule[l][1] = yat[j*nsite+l]
				molecule[l][2] = zat[j*nsite+l]

			zeta1 = zmol[j] - zR - int_z_mol[0][j] 
			zeta2 = - zmol[j] + zR + int_z_mol[1][j]

			"""NORMAL Z AXIS"""

			O = ut.local_frame_molecule(molecule, model)
			if O[2][2] < -1: O[2][2] = -1.0
			elif O[2][2] > 1: O[2][2] = 1.0

			""" INTRINSIC SURFACE DERIVATIVE """
			#"""
			T = ut.local_frame_surface(dzx1, dzy1, -1)
			R1 = np.dot(O, np.linalg.inv(T))
			if R1[2][2] < -1: R1[2][2] = -1.0
			elif R1[2][2] > 1: R1[2][2] = 1.0

			T = ut.local_frame_surface(dzx2, dzy2, 1)
			R2 = np.dot(O, np.linalg.inv(T))
			if R2[2][2] < -1: R2[2][2] = -1.0
			elif R2[2][2] > 1: R2[2][2] = 1.0
			#"""

			int_index1 = int((zeta1 + DIM[2]/2) * nslice / DIM[2]) % nslice
			int_index2 = int((zeta2 + DIM[2]/2) * nslice / DIM[2]) % nslice

			for k in xrange(3):
				for l in xrange(3):
					index2 = k * 3 + l 
					temp_int_O[int_index1][index2] += R1[k][l]**2
					temp_int_O[int_index2][index2] += R2[k][l]**2

		with file('{}/INTEULER/{}_ODIST.npy'.format(directory, file_name_euler), 'w') as outfile:
			np.save(outfile, temp_int_O)

	return temp_int_O


def cw_gamma_1(q, gamma, kappa): return gamma + kappa * q**2


def cw_gamma_2(q, gamma, kappa0, l0): return gamma + q**2 * (kappa0 + l0 * np.log(q))


def cw_gamma_dft(q, gamma, kappa, eta0, eta1): return gamma + eta0 * q + kappa * q**2 + eta1 * q**3


def cw_gamma_sk(q, gamma, w0, r0, dp): return gamma + np.pi/32 * w0 * r0**6 * dp**2 * q**2 * (np.log(q * r0 / 2.) - (3./4 * 0.5772))


def intrinsic_mol_angles(directory, model, csize, frame, nslice, npi, nmol, COM, DIM, nsite, nm, qm, n0, phi, psi, recon, ow_angle):

	dpi = np.pi / npi

	temp_int_P_z_theta_phi = np.zeros((nslice, npi, npi*2))

	if recon:
		file_name_euler = '{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5),frame)
		file_name_pos = '{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_coeff = '{}_{}_{}_{}_{}_R'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)
	else: 
		file_name_euler = '{}_{}_{}_{}_{}_{}_{}'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5), frame)	
		file_name_pos = '{}_{}_{}_{}_{}_{}'.format(model.lower(), nm, qm, n0, int(1/phi + 0.5), frame)
		file_name_coeff = '{}_{}_{}_{}_{}'.format(model.lower(), nm, n0, int(1./phi + 0.5), frame)

	if os.path.exists('{}/INTEULER/{}_ANGLE1.npy'.format(directory, file_name_pos)) and not ow_angle:	
		try:
			with file('{}/INTEULER/{}_ANGLE1.npy'.format(directory, file_name_pos), 'r') as infile:
				zeta_array1, int_theta1, int_phi1, int_varphi1 = np.load(infile)
			with file('{}/INTEULER/{}_ANGLE2.npy'.format(directory, file_name_pos), 'r') as infile:
				zeta_array2, int_theta2, int_phi2, int_varphi2 = np.load(infile)

			for j in xrange(nmol):
				z = zeta_array1[j] + DIM[2]/2.
				index1 = int(z * nslice / DIM[2]) % nslice
				index2 = int(int_theta1[j] /dpi)
				index3 = int((int_phi1[j] + np.pi / 2.) / dpi) 

				try: temp_int_P_z_theta_phi[index1][index2][index3] += 1
				except IndexError: pass

				z = zeta_array2[j] + DIM[2]/2.
				index1 = int(z * nslice / DIM[2]) % nslice
				index2 = int(int_theta2[j] / dpi)
				index3 = int((int_phi2[j] + np.pi / 2.) / dpi)  

				try: temp_int_P_z_theta_phi[index1][index2][index3] += 1
				except IndexError: pass

		except Exception: ow_angle = True

	else: ow_angle = True

	if ow_angle:

		zeta_array1 = np.zeros(nmol)
		int_theta1 = np.zeros(nmol)
		int_phi1 = np.zeros(nmol)
		int_varphi1 = np.zeros(nmol)

		zeta_array2 = np.zeros(nmol)
		int_theta2 = np.zeros(nmol)
		int_phi2 = np.zeros(nmol)
		int_varphi2 =np.zeros(nmol)

		try:
			with file('{}/INTPOS/{}_INTZ_MOL.npy'.format(directory, file_name_pos), 'r') as infile:
				int_z_mol = np.load(infile)	
			with file('{}/INTPOS/{}_INTDXDY_MOL.npy'.format(directory, file_name_pos), 'r') as infile:
				dxdyz_mol = np.load(infile)
		except:
			with file('{}/ACOEFF/{}_INTCOEFF.npy'.format(directory, file_name_coeff), 'r') as infile: 
				auv1, auv2 = np.load(infile)
			int_z_at, int_z_mol, dxdyz_mol, ddxddyz_mol = intrinsic_positions_dxdyz(directory, model, csize, frame, auv1, auv2, nsite, nm, qm, n0, phi, psi, DIM, recon, False)

		xat, yat, zat = ut.read_atom_positions(directory, model, csize, frame)
		xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)
		xR, yR, zR = COM[frame]

		for j in xrange(nmol):
			sys.stdout.write("PROCESSING {} INTRINSIC ANGLES {}: nm = {} qm = {}  {} out of {}  molecules\r".format(directory, frame, nm, qm, j, nmol) )
			sys.stdout.flush()

			molecule = np.zeros((nsite, 3))

			for l in xrange(nsite):
				molecule[l][0] = xat[j*nsite+l]
				molecule[l][1] = yat[j*nsite+l]
				molecule[l][2] = zat[j*nsite+l]

			zeta1 = zmol[j] - zR - int_z_mol[0][j] 
			zeta2 = - zmol[j] + zR + int_z_mol[1][j]

			dzx1 = dxdyz_mol[0][j]
			dzy1 = dxdyz_mol[1][j]
			dzx2 = dxdyz_mol[2][j]
			dzy2 = dxdyz_mol[3][j]

			"""NORMAL Z AXIS"""

			O = ut.local_frame_molecule(molecule, model)
			if O[2][2] < -1: O[2][2] = -1.0
		        elif O[2][2] > 1: O[2][2] = 1.0

			#print "\n{} {} {}".format(np.arccos(O[2][2]), np.arctan(-O[2][0]/O[2][1]), np.arctan(O[0][2]/O[1][2]))
		
			""" INTRINSIC SURFACE """
			"""
			zeta_array1[j] = zeta1
			int_theta1[j] = np.arccos(O[2][2])
			int_phi1][j] = np.arctan2(-O[2][0],O[2][1])
			int_varphi1[j] = np.arctan2(O[0][2],O[1][2])

			zeta_array2[j] = zeta2
			int_theta2[j] = np.arccos(O[2][2])
			int_phi2[j] = np.arctan2(-O[2][0],O[2][1])
			int_varphi2[j] = np.arctan2(O[0][2],O[1][2])
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

			z = zeta_array1[j] + DIM[2]/2.
			index1 = int(z * nslice / DIM[2]) % nslice
			index2 = int(int_theta1[j] /dpi)
			index3 = int((int_phi1[j] + np.pi / 2.) / dpi) 

			try: temp_int_P_z_theta_phi[index1][index2][index3] += 1
			except IndexError: pass

			z = zeta_array2[j] + DIM[2]/2.
			index1 = int(z * nslice / DIM[2]) % nslice
			index2 = int(int_theta2[j] / dpi)
			index3 = int((int_phi2[j] + np.pi / 2.) / dpi)  

			try: temp_int_P_z_theta_phi[index1][index2][index3] += 1
			except IndexError: pass

		with file('{}/INTEULER/{}_ANGLE1.npy'.format(directory, file_name_pos), 'w') as outfile:
			np.save(outfile, (zeta_array1, int_theta1, int_phi1, int_varphi1))
		with file('{}/INTEULER/{}_ANGLE2.npy'.format(directory, file_name_pos), 'w') as outfile:
			np.save(outfile, (zeta_array2, int_theta2, int_phi2, int_varphi2))

	return temp_int_P_z_theta_phi


def intrinsic_angle_dist(nslice, npi, int_P_z_theta_phi):

	print "BUILDING ANGLE DISTRIBUTIONS"

	dpi = np.pi / npi

	print ""
	print "NORMALISING GRID"
	for index1 in xrange(nslice): 
		if np.sum(int_P_z_theta_phi[index1]) != 0: int_P_z_theta_phi[index1] = int_P_z_theta_phi[index1] / np.sum(int_P_z_theta_phi[index1])

	int_P_z_phi_theta = np.rollaxis(np.rollaxis(int_P_z_theta_phi, 2), 1)
	
	X_theta = np.arange(0, np.pi, dpi)
	X_phi = np.arange(-np.pi / 2, np.pi / 2, dpi)

	int_av_theta = np.zeros(nslice)
        int_av_phi = np.zeros(nslice)
	int_P1 = np.zeros(nslice)
	int_P2 = np.zeros(nslice)

	print "BUILDING AVERAGE ANGLE PROFILES"

	for index1 in xrange(nslice):
		sys.stdout.write("PROCESSING AVERAGE ANGLE PROFILES {} out of {} slices\r".format(index1, nslice) )
		sys.stdout.flush() 

		for index2 in xrange(npi):
			int_av_theta[index1] += np.sum(int_P_z_theta_phi[index1][index2]) * X_theta[index2] 
			int_P1[index1] += np.sum(int_P_z_theta_phi[index1][index2]) * np.cos(X_theta[index2])
			int_P2[index1] += np.sum(int_P_z_theta_phi[index1][index2]) * 0.5 * (3 * np.cos(X_theta[index2])**2 - 1)

			int_av_phi[index1] += np.sum(int_P_z_phi_theta[index1][index2]) * (X_phi[index2]) 

		if int_av_theta[index1] == 0: 
			int_av_theta[index1] += np.pi / 2.
			int_av_phi[index1] += np.pi / 4.

	a_dist = (int_av_theta, int_av_phi, int_P1, int_P2)
	
	return a_dist


def intrinsic_polarisability(nslice, a, count_int_O, av_int_O):

	int_axx = np.zeros(nslice)
	int_azz = np.zeros(nslice)

	for n in xrange(nslice):
		if count_int_O[n] != 0:
			av_int_O[n] *= 1./ count_int_O[n]
			for j in xrange(3):
				int_axx[n] += a[j] * 0.5 * (av_int_O[n][j] + av_int_O[n][j+3]) 
				int_azz[n] += a[j] * av_int_O[n][j+6] 
		else: 					
			int_axx[n] = np.mean(a)					
			int_azz[n] = np.mean(a)

	polar = (int_axx, int_azz)

	return polar



def intrinsic_profile(directory, model, csize, nframe, natom, nmol, nsite, AT, M, a_type, mol_sigma, COM, DIM, nslice, ncube, nm, QM, n0, phi, npi, vlim, ow_profile, ow_auv, ow_recon, ow_pos, ow_dxdyz, ow_dist, ow_count, ow_angle, ow_polar):

	if model.lower() == 'argon': T = 85
	else: T = 298

	lslice = DIM[2] / nslice
	Aslice = DIM[0]*DIM[1]
	Vslice = DIM[0]*DIM[1]*lslice
	Acm = 1E-8
	ur = 1
	Z1 = np.linspace(0, DIM[2], nslice)
	Z2 = np.linspace(-DIM[2]/2, DIM[2]/2, nslice)
	NZ = np.linspace(0, 1, 100)
	n_waves = 2 * nm + 1
	psi = phi * DIM[0] * DIM[1]

	atom_types = list(set(AT))
	n_atom_types = len(atom_types)

	a = ut.get_polar_constants(model, a_type)

	av_auv1 = np.zeros((2, nframe))
	av_auv2 = np.zeros((2, nframe))

	av_auv1_2 = np.zeros((2, n_waves**2))
	av_auv2_2 = np.zeros((2, n_waves**2))

	av_auvU_2 = np.zeros((2, n_waves**2))
        av_auvP_2 = np.zeros((2, n_waves**2))

	tot_auv1 = np.zeros((2, nframe, n_waves**2))
	tot_auv2 = np.zeros((2, nframe, n_waves**2))

	with file('{}/DEN/{}_{}_{}_PAR.npy'.format(directory, model.lower(), nslice, nframe), 'r') as infile:
                param = np.load(infile)
	
	for frame in xrange(nframe):

		tot_auv1[0][frame], tot_auv2[0][frame], tot_auv1[1][frame],tot_auv2[1][frame], piv_n1, piv_n2 = intrinsic_surface(directory, model, csize, nsite, nmol, ncube, DIM, COM, nm, n0, phi, psi, vlim, mol_sigma, M, frame, nframe, ow_auv, ow_recon)		

		for i in xrange(2):
			av_auv1_2[i] += tot_auv1[i][frame]**2 / nframe
			av_auv2_2[i] += tot_auv2[i][frame]**2 / nframe

			av_auv1[i][frame] = tot_auv1[i][frame][n_waves**2/2]
			av_auv2[i][frame] = tot_auv2[i][frame][n_waves**2/2]

			av_auvU_2[i] += (tot_auv1[i][frame] + tot_auv2[i][frame])**2/ (4. * nframe)
			av_auvP_2[i] += (tot_auv1[i][frame] - tot_auv2[i][frame])**2/ (4. * nframe)


	AU = [np.zeros(len(QM)), np.zeros(len(QM))]
	AP = [np.zeros(len(QM)), np.zeros(len(QM))]
	ACU = [np.zeros(len(QM)), np.zeros(len(QM))]

	Q_set = []

	cw_gammaU = [[], []]
	cw_gammaP = [[], []]
	cw_gammaCU = [[], []]

	av_auvCU_2 = np.array([av_auvP_2[0] - av_auvU_2[0], av_auvP_2[1] - av_auvU_2[1]])

	tot_auv1 = np.array([np.transpose(tot_auv1[0]), np.transpose(tot_auv2[1])])
	tot_auv2 = np.array([np.transpose(tot_auv2[0]), np.transpose(tot_auv2[1])])

	file_name = ['{}_{}_{}_{}_{}'.format(model.lower(), nm, n0, int(1/phi + 0.5), nframe), 
		     '{}_{}_{}_{}_{}_R'.format(model.lower(), nm, n0, int(1/phi + 0.5), nframe)]

	for r, recon in enumerate([False, True]):
		if not os.path.exists('{}/INTTHERMO/{}_HYDRO.npy'.format(directory, file_name[r])) or False:
			tot_Gamma1, tot_omega1 = auv_correlation(tot_auv1[r], nm)
			tot_Gamma2, tot_omega2 = auv_correlation(tot_auv2[r], nm)

			with file('{}/INTTHERMO/{}_HYDRO.npy'.format(directory, file_name[r]), 'w') as outfile:
		                np.save(outfile, (tot_Gamma1, tot_omega1, tot_Gamma2, tot_omega2))
	
	with file('{}/INTTHERMO/{}_HYDRO.npy'.format(directory, file_name[0]), 'r') as infile:
		tot_Gamma1, tot_omega1, tot_Gamma2, tot_omega2 = np.load(infile)
	with file('{}/INTTHERMO/{}_HYDRO.npy'.format(directory, file_name[1]), 'r') as infile:
		tot_Gamma1_recon, tot_omega1_recon, tot_Gamma2_recon, tot_omega2_recon = np.load(infile)

	for j, qm in enumerate(QM):

		q_set = []
		q2_set = []

		for u in xrange(-qm, qm):
			for v in xrange(-qm, qm):
				q = 4 * np.pi**2 * (u**2 / DIM[0]**2 + v**2/DIM[1]**2)
				q2 = u**2 * DIM[1]/DIM[0] + v**2 * DIM[0]/DIM[1]

				if q2 not in q2_set:
					q_set.append(q)
					q2_set.append(np.round(q2, 4))

		q_set = np.sqrt(np.sort(q_set, axis=None))
		q2_set = np.sort(q2_set, axis=None)
		Q_set.append(q_set)

		for r, recon in enumerate([False, True]):
			AU[r][j] = (slice_area(av_auvU_2[r], nm, qm, DIM))
		        AP[r][j] = (slice_area(av_auvP_2[r], nm, qm, DIM))
			ACU[r][j] = (slice_area(av_auvCU_2[r], nm, qm, DIM))

			cw_gammaU[r].append(gamma_q_auv(av_auvU_2[r]*2, nm, qm, DIM, T, q2_set))
		        cw_gammaP[r].append(gamma_q_auv(av_auvP_2[r]*2, nm, qm, DIM, T, q2_set))
			cw_gammaCU[r].append(gamma_q_auv(av_auvCU_2[r], nm, qm, DIM, T, q2_set))
	
		#Gamma_hist1, omega_hist1 = get_hydro_param(tot_Gamma1, tot_omega1, nm, qm, DIM, q2_set)
		#Gamma_hist2, omega_hist2 = get_hydro_param(tot_Gamma2, tot_omega2, nm, qm, DIM, q2_set)
		#Gamma_hist1_recon, omega_hist1_recon = get_hydro_param(tot_Gamma1_recon, tot_omega1_recon, nm, qm, DIM, q2_set)
		#Gamma_hist2_recon, omega_hist2_recon = get_hydro_param(tot_Gamma2_recon, tot_omega2_recon, nm, qm, DIM, q2_set)

		if qm == nm:
			file_name_gamma = ['{}_{}_{}_{}_{}'.format(model.lower(), nm, n0, int(1/phi + 0.5), nframe),
					'{}_{}_{}_{}_{}_R'.format(model.lower(), nm, n0, int(1/phi + 0.5), nframe)]

			for r, recon in enumerate([False, True]):
				with file('{}/INTTHERMO/{}_GAMMA.npy'.format(directory, file_name_gamma[r]), 'w') as outfile:
					np.save(outfile, (Q_set[-1], cw_gammaU[r][-1], cw_gammaP[r][-1], cw_gammaCU[r][-1]))
			

		file_name_die = ['{}_{}_{}_{}_{}_{}_{}_{}'.format(model.lower(), a_type, nslice, nm, qm, n0, int(1/phi + 0.5), nframe), 
		    		 '{}_{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), a_type, nslice, nm, qm, n0, int(1/phi + 0.5), nframe)]
		file_name_den = ['{}_{}_{}_{}_{}_{}_{}'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5), nframe), 
		    		 '{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nslice, nm, qm, n0, int(1/phi + 0.5), nframe)]

		if not os.path.exists('{}/INTDIELEC/{}_DIE.npy'.format(directory, file_name_die[1])) or ow_profile:

			for r, recon in enumerate([False, True]):

				Delta1 = (ut.sum_auv_2(av_auv1_2[r], nm, qm) - np.mean(av_auv1[r])**2)
				Delta2 = (ut.sum_auv_2(av_auv2_2[r], nm, qm) - np.mean(av_auv2[r])**2)
				#DeltaU = (ut.sum_auv_2(av_auvU_2[r], nm, qm) - np.mean(av_auvU[r])**2)
				#DeltaP = (ut.sum_auv_2(av_auvP_2[r], nm, qm) - np.mean(av_auvP[r])**2)
				DeltaCU = (ut.sum_auv_2(av_auvCU_2[r], nm, qm) - np.mean(av_auv1[r])*np.mean(av_auv2[0]))

				if not os.path.exists('{}/INTDEN/{}_MOL_DEN.npy'.format(directory, file_name_den[r])) or ow_dist: 

					av_den_corr_matrix = np.zeros((nslice, 100))
	       				av_z_nz_matrix = np.zeros((100, 100))	

					count_int_O = np.zeros((nslice))
					av_int_O = np.zeros((nslice, 9))

					int_P_z_theta_phi = np.zeros((nslice, npi, npi*2))

					for frame in xrange(nframe):
						sys.stdout.write("PROCESSING FRAME {}\r".format(frame))
						sys.stdout.flush()

						int_count_corr_array, int_count_z_nz = intrinsic_z_den_corr(directory, COM, model, csize, nm, qm, n0, phi, psi, frame, nslice, nsite, DIM, recon, ow_count)
						av_den_corr_matrix += int_count_corr_array
						av_z_nz_matrix += int_count_z_nz
			
						if model.upper() != 'ARGON':

							temp_int_P_z_theta_phi = intrinsic_mol_angles(directory, model, csize, frame, nslice, npi, nmol, COM, DIM, nsite, nm, qm, n0, phi, psi, recon, ow_angle)
							int_P_z_theta_phi += temp_int_P_z_theta_phi

							temp_int_O = intrinsic_R_tensors(directory, model, csize, frame, nslice, COM, DIM, nsite, nm, qm, n0, phi, psi, recon, ow_polar)
							av_int_O += temp_int_O

					N = np.linspace(0, 50 * lslice, 100)

					P_z_nz = av_z_nz_matrix * 2 / (np.sum(av_z_nz_matrix) * 0.01 * lslice)
					P_den_corr_matrix = av_den_corr_matrix / np.sum(av_den_corr_matrix)
					P_corr = np.array([np.sum(A) for A in np.transpose(P_den_corr_matrix)])

					int_den_corr = av_den_corr_matrix / (2 * nframe * Vslice)
					mol_int_den = np.array([np.sum(A) for A in int_den_corr])
					count_int_O = np.array([np.sum(A) for A in av_den_corr_matrix])

					with file('{}/INTDEN/{}_MOL_DEN.npy'.format(directory, file_name_den[r]), 'w') as outfile:
						np.save(outfile, mol_int_den)
					with file('{}/INTDEN/{}_MOL_DEN_CORR.npy'.format(directory, file_name_den[r]), 'w') as outfile:
						np.save(outfile, int_den_corr)

					if model.upper() != 'ARGON':

						int_axx, int_azz = intrinsic_polarisability(nslice, a, count_int_O, av_int_O)
						int_av_theta, int_av_phi, int_P1, int_P2 = intrinsic_angle_dist(nslice, npi, int_P_z_theta_phi)

						with file('{}/INTEULER/{}_INT_EUL.npy'.format(directory, file_name_die[r]), 'w') as outfile:
							np.save(outfile, (int_axx, int_azz, int_av_theta, int_av_phi, int_P1, int_P2))

				else:
					with file('{}/INTDEN/{}_MOL_DEN.npy'.format(directory, file_name_den[r]), 'r') as infile:
						mol_int_den = np.load(infile)
		
					if model.upper() != 'ARGON':
						with file('{}/INTEULER/{}_INT_EUL.npy'.format(directory, file_name_die[r]), 'r') as infile:
							int_axx, int_azz, int_av_theta, int_av_phi, int_P1, int_P2 = np.load(infile)

				if model.upper() == 'ARGON':

					int_axx = np.ones(nslice) * a
					int_azz = np.ones(nslice) * a

				print Delta1, Delta2, DeltaCU

				rho_axx =  np.array([mol_int_den[n] * int_axx[n] for n in range(nslice)])
				rho_azz =  np.array([mol_int_den[n] * int_azz[n] for n in range(nslice)])

				int_exx = np.array([(1 + 8 * np.pi / 3. * rho_axx[n]) / (1 - 4 * np.pi / 3. * rho_axx[n]) for n in range(nslice)])
				int_ezz = np.array([(1 + 8 * np.pi / 3. * rho_azz[n]) / (1 - 4 * np.pi / 3. * rho_azz[n]) for n in range(nslice)])

				int_no = np.sqrt(ur * int_exx)
				int_ni = np.sqrt(ur * int_ezz)

				centres = np.ones(9) * (np.mean(av_auv1[r]) - np.mean(av_auv2[r]))/2.
				deltas = np.ones(9) * 0.5 * (Delta1 + Delta2)

				arrays = [mol_int_den, int_axx, int_azz, rho_axx, rho_azz, int_exx, int_ezz, int_no, int_ni]

				cw_arrays = ut.gaussian_smoothing(arrays, centres, deltas, DIM, nslice)

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
				"""
				plt.figure(r)
				plt.plot(np.sqrt(cw_exx1))
				plt.plot(np.sqrt(cw_exx2))
				plt.plot(np.sqrt(cw_arrays[5]))
				plt.plot(cw_arrays[7])
				#"""

				print '\n'
				print "WRITING TO FILE... nm = {}  qm = {}  var1 = {}  var2 = {}".format(nm, qm, Delta1, Delta2)

				with file('{}/INTDEN/{}_EFF_DEN.npy'.format(directory, file_name_den[r]), 'w') as outfile:
					np.save(outfile, cw_arrays[0])
				with file('{}/INTDIELEC/{}_DIE.npy'.format(directory, file_name_die[r]), 'w') as outfile:
					np.save(outfile, (int_exx, int_ezz))
				with file('{}/INTDIELEC/{}_CWDIE.npy'.format(directory, file_name_die[r]), 'w') as outfile:
					np.save(outfile, (cw_exx1, cw_ezz1, cw_exx2, cw_ezz2, cw_arrays[5], cw_arrays[6], cw_arrays[7]**2, cw_arrays[8]**2))
				with file('{}/ELLIP/{}_ELLIP_NO.npy'.format(directory, file_name_die[r]), 'w') as outfile:
					np.save(outfile, (np.sqrt(cw_exx1), np.sqrt(cw_exx2), np.sqrt(cw_arrays[5]), cw_arrays[7]))
			#plt.show()

	print "INTRINSIC SAMPLING METHOD {} {} {} {} {} {} COMPLETE\n".format(directory, model.upper(), nm, qm, n0, phi)


	"""	
	#for j, qm in enumerate(QM):
	plt.figure(1)
	plt.scatter(Q_set[-1], gammaU[-1])
	plt.figure(2)
	plt.scatter(Q_set[-1], gammaP[-1])
	plt.figure(3)
	for j, qm in enumerate(QM):
		plt.scatter(Q_set[j], gammaCU[j])
	plt.show()
	"""

	return av_auv1, av_auv2 
