"""
*************** ELLIPSOMETRY MODULE *******************

PROGRAM INPUT:
	       

PROGRAM OUTPUT: 
		
		

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
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, zoomed_inset_axes, mark_inset, InsetPosition

import utilities as ut

sys.path.append('/data/fl7g13/tmm-0.1.5/')
import tmm_core
import csv

ERROR = sys.float_info.epsilon

def ellips(n, theta, lam_vac, d_list, nlayers, pol, var=0):

	angles = snell_angle_array(n, theta)
	kz_list = 2 * np.pi * n * np.cos(angles) / lam_vac
	delta = kz_list * d_list

	#print np.max(delta[1:-1]), var, 2 * np.max(delta[1:-1])**2 * var, np.exp(2 * np.max(delta[1:-1])**2 * var)

	t_list = np.zeros((nlayers, nlayers), dtype=complex)
	r_list = np.zeros((nlayers, nlayers), dtype=complex)

	M_list = np.zeros((nlayers, 2, 2), dtype=complex)

	Mtilde = np.array([[1,0], [0,1]], dtype=complex)

	r_list[0][1], t_list[0][1] = get_ref_tran(pol, n[0], n[1], angles[0], angles[1])

	for i in xrange(1, nlayers-3):
		j = i+1
		r_list[i][j], t_list[i][j] = get_ref_tran(pol, n[i], n[j], angles[i], angles[j])

		Mn1 = np.array([[np.exp(-1j*delta[i]), 0], [0, np.exp(1j*delta[i])]], dtype=complex)

		if var != 0:
			Mn2 = np.array([[1.0,  r_list[i][j] * np.exp(2 * delta[j]**2 * var)], 
					[r_list[i][j] * np.exp(-2 * delta[i]**2 * var), np.exp(- 2 * (delta[i] - delta[j])**2 * var)]], dtype=complex)
			M_list[i] = (np.exp((delta[i] - delta[j])**2 * var / 2.) / t_list[i][j]) * np.dot(Mn1, Mn2)
		else:
			Mn2 = np.array([[1, r_list[i][j]], [r_list[i][j], 1]], dtype=complex)
			M_list[i] = (1. / t_list[i][j]) * np.dot(Mn1, Mn2)

		Mtilde = np.dot(Mtilde, M_list[i])

	for i in xrange(nlayers-3, nlayers-1):
		j = i+1
		r_list[i][j], t_list[i][j] = get_ref_tran(pol, n[i], n[j], angles[i], angles[j])
		Mn1 = np.array([[np.exp(-1j*delta[i]), 0], [0, np.exp(1j*delta[i])]], dtype=complex)
		Mn2 = np.array([[1, r_list[i][j]], [r_list[i][j], 1]], dtype=complex)
		M_list[i] = (1. / t_list[i][j]) * np.dot(Mn1, Mn2)
		Mtilde = np.dot(Mtilde, M_list[i])

	Mtilde = np.dot(np.array([[1, r_list[0][1]], [r_list[0][1], 1]], dtype=complex) / t_list[0][1], Mtilde)
	
	r = Mtilde[0][1] / Mtilde[0][0]
	t = 1 / Mtilde[0][0]

	return r, t


def snell_angle_array(n, theta_0):

	angles = sp.arcsin(np.real_if_close(n[0] / n * np.sin(theta_0)))
	if not check_forward_angle(n[0], angles[0]): angles[0] = np.pi - angles[0]
	if not check_forward_angle(n[-1], angles[-1]): angles[-1] = np.pi - angles[-1]

	return angles


def check_forward_angle(n_i, theta_i):

	n_cos_theta = n_i * np.cos(theta_i)

	if abs(n_cos_theta.imag) > 100 * ERROR: answer = bool(n_cos_theta.imag > 0)
	else: answer = bool(n_cos_theta.real > 0)

	return answer


def get_ref_tran(pol, n_1, n_2, theta_1, theta_2):

	if pol == 's':
		denom = (n_1 * np.cos(theta_1) + n_2 * np.cos(theta_2))
		r = (n_1 * np.cos(theta_1) - n_2 * np.cos(theta_2)) / denom
	if pol == 'p':
		denom = (n_2 * np.cos(theta_1) + n_1 * np.cos(theta_2))
		r = (n_2 * np.cos(theta_1) - n_1 * np.cos(theta_2)) / denom

	t = 2 * n_1 * np.cos(theta_1) / denom

	return r, t


def n_func(x, a, b, c): return a*(x-b)**2 + c


def den_func(z, nv, nl, z0, d): return 0.5 * (nl + nv) - 0.5 * (nl - nv) * np.tanh((z - z0)/ (2*d))


def den_func2(z, m, s1, s2, d): return 0.5 * (m + 1) - 0.5 * (m - 1) * (np.tanh((z - s1)/ (2*d)) * np.tanh((z - s2)/ (2*d)))


def increase_deriv(m, n, Z):

	range_ = Z[-1] - Z[0]
	nslice = len(Z)

	new_n = copy.copy(n)

	for i in xrange(1,nslice):
		dn = n[i]-n[i-1]
		new_n[i] = n[i-1] + dn * m

	return new_n 

def load_experimental(wkdir):

	nruns = 10
	start_lam =200
	end_lam = 1000
	lambda_list = np.linspace(start_lam,end_lam,100)

	theta1 = np.arange(40,71)
	theta2 = np.arange(50, 55.01, 0.1)
	theta3 = np.linspace(52.0, 54.00, 21) 
	theta4 = np.linspace(51.5, 53.50, 21) 

	psi_w = np.zeros((nruns, 21))
	delta_w = np.zeros((nruns, 21))
	theta_w = np.array((theta3+0.2, theta3, theta3, theta3+0.2, theta3, theta3, theta3+0.7, theta3+0.7, theta3+0.2, theta4+0.7))	

	theta_m = np.zeros((2, 21))
	psi_m = np.zeros((2, 21))
	delta_m = np.zeros((2, 21))

	with file("{}/datasheets/water_ellipsometry_data_psi.csv".format(wkdir), 'r') as infile:
		psi_w[0], psi_w[1], psi_w[2], _, psi_w[3], psi_w[4], psi_w[5], psi_w[6], psi_w[7], psi_w[8], psi_w[9] = np.loadtxt(infile)
	with file("{}/datasheets/water_ellipsometry_data_delta.csv".format(wkdir), 'r') as infile:
		delta_w[0], delta_w[1], delta_w[2], _, delta_w[3], delta_w[4], delta_w[5], delta_w[6], delta_w[7], delta_w[8], delta_w[9] = np.loadtxt(infile)
	with file("{}/datasheets/methanol_ellipsometry_data_theta.csv".format(wkdir), 'r') as infile:
		theta_m[0], theta_m[1] = np.loadtxt(infile)
	with file("{}/datasheets/methanol_ellipsometry_data_psi.csv".format(wkdir), 'r') as infile:
		psi_m[0], psi_m[1] = np.loadtxt(infile)
	with file("{}/datasheets/methanol_ellipsometry_data_delta.csv".format(wkdir), 'r') as infile:
		delta_m[0], delta_m[1] = np.loadtxt(infile)
	with file("{}/datasheets/ethanol_ellipsometry_data_theta.csv".format(wkdir), 'r') as infile:
		theta_e = np.loadtxt(infile)
	with file("{}/datasheets/ethanol_ellipsometry_data_psi.csv".format(wkdir), 'r') as infile:
		psi_e = np.loadtxt(infile)
	with file("{}/datasheets/ethanol_ellipsometry_data_delta.csv".format(wkdir), 'r') as infile:
		delta_e = np.loadtxt(infile)
 	"""
	theta_e = np.arange(52.5, 54.51, 0.1)
	psi_e = [1.927, 1.772, 1.645, 1.495, 1.359, 1.221, 1.072, 0.934, 0.792, 0.625, 0.481, 0.334, 0.187, 0.074, 0.145, 0.269, 0.419, 0.558, 0.673, 0.824, 0.964 ]
	delta_e = [178.082, 177.911, 177.928, 178.004, 177.563, 177.192, 177.246, 176.199, 175.123, 174.095, 172.755, 171.083, 160.932, 126.738, 28.259, 12.762, 7.436, 5.611, 4.541, 4.125, 3.157]

	with file("datasheets/ethanol_ellipsometry_data_theta.csv", 'w') as outfile:
		np.savetxt(outfile, (theta_e), fmt='%-12.6f')
	with file("datasheets/ethanol_ellipsometry_data_psi.csv", 'w') as outfile:
		np.savetxt(outfile, (psi_e), fmt='%-12.6f')
	with file("datasheets/ethanol_ellipsometry_data_delta.csv", 'w') as outfile:
		np.savetxt(outfile, (delta_e), fmt='%-12.6f')
	"""

	av_theta_w = np.arange(np.min(theta_w), np.max(theta_w)+0.01, 0.1) 
	count_w = np.zeros(len(av_theta_w))
	av_psi_w = np.zeros(len(av_theta_w))
	av_delta_w = np.zeros(len(av_theta_w))

	av_theta_m = np.arange(np.min(theta_m), np.max(theta_m)+0.01, 0.1) 
	count_m = np.zeros(len(av_theta_m))
	av_psi_m = np.zeros(len(av_theta_m))
	av_delta_m = np.zeros(len(av_theta_m)) 

	for j, thej in enumerate(av_theta_m):
		for i in xrange(2):
			for k, thek in enumerate(theta_m[i]):				
				if abs(thej - thek) < 0.05:
					av_psi_m[j] += psi_m[i][k]
					av_delta_m[j] += delta_m[i][k]
					count_m[j] += 1
	
	for j, the in enumerate(av_theta_m):
		if count_m[j] != 0:
			av_psi_m[j] = av_psi_m[j] / count_m[j]
			av_delta_m[j] = av_delta_m[j] / count_m[j]

	for j, thej in enumerate(av_theta_w):
		for i in xrange(nruns):
			for k, thek in enumerate(theta_w[i]):
				#try:
				#print thej - thek 				
				if abs(thej - thek) < 0.05:
					av_psi_w[j] += psi_w[i][k]
					av_delta_w[j] += delta_w[i][k]
					count_w[j] += 1
				#except ValueError: pass
	
	for j, the in enumerate(av_theta_w):
		if count_w[j] != 0:
			av_psi_w[j] = av_psi_w[j] / count_w[j]
			av_delta_w[j] = av_delta_w[j] / count_w[j]


	n = [1.396+1.10E-7j, 1.373+4.9E-8j, 1.362+3.35E-8j, 1.354+2.35E-8j, 1.349+1.6E-8j, 1.346+1.08E-8j, 1.343+6.5E-9j, 1.341+3.5E-9j, 
	     1.339+1.86E-9j, 1.338+1.3E-9j, 1.337+1.02E-9j, 1.336+9.35E-10j, 1.335+1.00E-9j, 1.334+1.32E-9j, 1.333+1.96E-9j, 
             1.333+3.60E-9j, 1.332+1.09E-8j, 1.332+1.39E-8j, 1.331+1.64E-8j, 1.331+2.23E-8j, 1.331+3.35E-8j, 1.330+9.15E-8j,
	     1.330+1.56E-7j, 1.330+1.48E-7j, 1.329+1.25E-7j, 1.329+1.82E-7j, 1.329+2.93E-7j, 1.328+3.91E-7j, 1.328+4.86E-7j,
	     1.328+1.06E-6j, 1.327+2.93E-6j, 1.327+3.48E-6j, 1.327+2.89E-6j]
	k = np.linspace(start_lam,end_lam,len(n))

	real_param, _ = curve_fit(n_func, k , np.real(n), [1.331, 700, 1.331])
	real_n = map (lambda x: real_param[0]*(x-real_param[1])**2 + real_param[2], lambda_list)
	imag_param, _ = curve_fit(n_func, k , np.imag(n), [5E-13, 450, 5E-13])
	imag_n = map (lambda x: imag_param[0]*(x-imag_param[1])**2 + imag_param[2], lambda_list)

	EXPERIMENT = {'TIP4P2005': (av_theta_w, av_psi_w, av_delta_w, theta_w, psi_w, delta_w ),
		      'SPCE': (av_theta_w, av_psi_w, av_delta_w, theta_w, psi_w, delta_w ),
		      'AMOEBA': (av_theta_w, av_psi_w, av_delta_w, theta_w, psi_w, delta_w ),
		      'METHANOL': (av_theta_m, av_psi_m, av_delta_m, theta_m, psi_m, delta_m), 
		      'ETHANOL' : (psi_e, delta_e, theta_e, theta_e, psi_e, delta_e)}

	return EXPERIMENT

def load_theoretical(directory, model, nslice, a_type, DIM, nframe, angles):

	with file('{}/DIELEC/{}_{}_{}_{}_ELLIP_NO.npy'.format(directory, model.lower(), a_type, nslice, nframe), 'r') as infile:
                no, ni = np.load(infile)
        with file('{}/DIELEC/{}_{}_{}_{}_ELLIP_NO_SM.npy'.format(directory, model.lower(), a_type, nslice, nframe), 'r') as infile:
                no_sm, ni_sm = np.load(infile)

	nangle = len(angles)

	exx = no**2
        ezz = ni**2

        exx_sm = no_sm**2
        ezz_sm = ni_sm**2

	ne = np.zeros((nangle, nslice/2))
	ne_sm = np.zeros((nangle, nslice/2))

	for i, theta in enumerate(angles):
		anis = np.array([1 - (ezz[n] - exx[n]) * np.sin(theta)**2 / ezz[n] for n in range(nslice/2)])
                ne[i] += np.array([np.sqrt(exx[n] / anis[n]) for n in range(nslice/2)])

                anis = np.array([1 - (ezz_sm[n] - exx_sm[n]) * np.sin(theta)**2 / ezz_sm[n] for n in range(nslice/2)])
                ne_sm[i] += np.array([np.sqrt(exx_sm[n] / anis[n]) for n in range(nslice/2)])

	no = no[:nslice/2]
	no_sm = no_sm[:nslice/2]

	no_array = [no, no_sm]
	ne_array = [ne, ne_sm]

	return no_array, ne_array


def load_theoretical_ism(directory, model, nslice, a_type, DIM, qm, n0, phi, nframe, angles, mean_auv):

	file_name_die = '{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), a_type, nslice, qm, n0, int(1/phi + 0.5), nframe)

	int_die = np.load('{}/INTDIELEC/{}_DIE.npy'.format(directory, file_name_die), mmap_mode='r')
	cw_die = np.load('{}/INTDIELEC/{}_CWDIE.npy'.format(directory, file_name_die), mmap_mode='r')
	ellip_no = np.load('{}/ELLIP/{}_ELLIP_NO.npy'.format(directory, file_name_die), mmap_mode='r')

	int_exx, int_ezz = np.moveaxis(int_die, 0, 1)
	cw_exx_A, cw_ezz_A, cw_exx_B, cw_ezz_B, cw_exx_C, cw_ezz_C, cw_exx_D, cw_ezz_D = np.moveaxis(cw_die, 0, 1)
	cw_no_A, cw_no_B, cw_no_C, cw_no_D = np.moveaxis(ellip_no, 0, 1)

	nangle = len(angles)

	shift = int(mean_auv / DIM[2] * nslice)

	int_exx = np.delete(np.roll(int_exx, shift, axis=1), np.s_[nslice/2:], axis=1)
	int_ezz = np.delete(np.roll(int_ezz, shift, axis=1), np.s_[nslice/2:], axis=1)

	cw_no_B = np.delete(cw_no_B, np.s_[nslice/2:], axis=1)
	cw_no_C = np.delete(cw_no_C, np.s_[nslice/2:], axis=1)
	cw_no_D = np.delete(cw_no_D, np.s_[nslice/2:], axis=1)

	cw_exx_B = np.delete(cw_exx_B, np.s_[nslice/2:], axis=1)
	cw_exx_C = np.delete(cw_exx_C, np.s_[nslice/2:], axis=1)
	cw_exx_D = np.delete(cw_exx_D, np.s_[nslice/2:], axis=1)

	cw_ezz_B = np.delete(cw_ezz_B, np.s_[nslice/2:], axis=1)
	cw_ezz_C = np.delete(cw_ezz_C, np.s_[nslice/2:], axis=1)
	cw_ezz_D = np.delete(cw_ezz_D, np.s_[nslice/2:], axis=1)

	int_no = np.sqrt(int_exx)

	cw_ne_B = np.zeros((qm+1, nangle, nslice/2))
	cw_ne_C = np.zeros((qm+1, nangle, nslice/2))
	cw_ne_D = np.zeros((qm+1, nangle, nslice/2))
	int_ne = np.zeros((qm+1, nangle, nslice/2))

	for qu in xrange(qm + 1):

		temp_file_name_die = '{}_{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), a_type, nslice, qm, qu, n0, int(1/phi + 0.5), nframe)
		try:
			os.remove('{}/INTDIELEC/{}_DIE.npy'.format(directory, temp_file_name_die))
			os.remove('{}/INTDIELEC/{}_CWDIE.npy'.format(directory, temp_file_name_die))
			os.remove('{}/INTDIELEC/{}_ELLIP_NO.npy'.format(directory, temp_file_name_die))
		except: pass		

		for i, theta in enumerate(angles):

			anis = 1 - (cw_ezz_B[qu] - cw_exx_B[qu]) * np.sin(theta)**2 / cw_ezz_B[qu]
			cw_ne_B[qu][i] += np.sqrt(cw_exx_B[qu] / anis)

			anis = 1 - (cw_ezz_C[qu] - cw_exx_C[qu]) * np.sin(theta)**2 / cw_ezz_C[qu]
			cw_ne_C[qu][i] += np.sqrt(cw_exx_C[qu]/ anis)

			anis = 1 - (cw_ezz_D[qu] - cw_exx_D[qu]) * np.sin(theta)**2 / cw_ezz_D[qu]
			cw_ne_D[qu][i] += np.sqrt(cw_exx_D[qu] / anis)

			anis = 1 - (int_ezz[qu] - int_exx[qu]) * np.sin(theta)**2 / int_ezz[qu]
			int_ne[qu][i] += np.sqrt(int_exx[qu] / anis)

	no_array = np.array((int_no, cw_no_B, cw_no_C, cw_no_D))
	ne_array = np.array((int_ne, cw_ne_B, cw_ne_C, cw_ne_D))

	exx_array = np.array((int_exx, cw_exx_B, cw_exx_C, cw_exx_D))
	ezz_array = np.array((int_ezz, cw_ezz_B, cw_ezz_C, cw_ezz_D))	

	
	return no_array, ne_array, exx_array, ezz_array


def ellip_capillary(auv_2, qm, qu, DIM):

	qxi2 = 0
	for u in xrange(-qu, qu+1):
                for v in xrange(-qu, qu+1):
                        j = (2 * qm + 1) * (u + qm) + (v + qm)
                        dot_prod = np.pi**2  * (u**2/DIM[0]**2 + v**2/DIM[1]**2)

			if abs(u) + abs(v) > 0:
                        	xi_2 = ut.check_uv(u, v) * auv_2[j] / 4.
                        	qxi2 += xi_2 * np.sqrt(dot_prod)

	return qxi2

def transfer_matrix(directory, model, csize, AT, sigma, mol_sigma, nslice, nframe, a_type, qm, QM, n0, phi, DIM, cutoff, scan_type=0):

	"INPUT DATA"

	wkdir = '/home/fl7g13/alias'
	groot = "{}/Figures/ELLIP".format(directory)
	if not os.path.exists(groot): os.mkdir(groot)

	EXPERIMENT = load_experimental(wkdir)

	""" FIGURE PARAMETERS """
	fig_x = 12
	fig_y = 8
	msize = 50
	plt.rc('text', usetex=True)
	plt.rc('font', family='serif', size='20.0')
	plt.rc('lines', linewidth='1.5', markersize=7)
	plt.rc('axes', labelsize='25.0')
	plt.rc('xtick', labelsize='25.0')
	plt.rc('ytick', labelsize='25.0')
	lnsp = 25.0

	degree = np.pi/180.

	lslice = DIM[2] / nslice
	nlayers = nslice/2

	lam_vac = 5145

	if model.upper() == 'ARGON':
		n_l = 1.2315 #A. C. Sinnock and B. L. Smith. Refractive indices of the condensed inert gases, Phys. Rev. 181, 1297-1307 (1969)
		start_angle = 50.5 
		end_angle = 51.2
	elif model.upper() == 'ETHANOL':
		start_angle = 52.5 
		end_angle = 54.5
		n_l = 1.3642 #E. Sani and A. Dell'Oro. Spectral optical constants of ethanol and isopropanol from ultraviolet to far infrared, Optical Materials 60, 137-141 (2016)
	elif model.upper() == 'METHANOL':
		start_angle = 52.4 
		end_angle = 54.5
		n_l = 1.3296 #K. Moutzouris, M. Papamichael, S. C. Betsis, I. Stavrakas, G. Hloupis and D. Triantis. Refractive, dispersive and thermo-optic properties of twelve organic solvents in the visible and near-infrared, Appl. Phys. B 116, 617-622 (2013)
	elif model.upper() == 'DMSO':
		start_angle = 55 
		end_angle = 57
		n_l = 1.4824 #Z. Kozma, P. Krok, and E. Riedle. Direct measurement of the group-velocity mismatch and derivation of the refractive-index dispersion for a variety of solvents in the ultraviolet, J. Opt. Soc. Am. B 22, 1479-1485 (2005)
	else:
		start_angle = 52.0 
		end_angle = 54.5
		n_l = 1.3344 #G. M. Hale and M. R. Querry. Optical constants of water in the 200-nm to 200-micm wavelength region, Appl. Opt. 12, 555-563 (1973)

	ref_brewster = np.real(np.arctan(n_l)) / degree

	n_angle = 100

	ellip_angles = np.linspace(start_angle * degree, end_angle * degree, n_angle)

	mean_auv1 = np.zeros(nframe)
	mean_auv2 = np.zeros(nframe)

	av_auv1_2 = np.zeros((2*qm+1)**2)
	av_auv2_2 = np.zeros((2*qm+1)**2)

	for frame in xrange(nframe):
		sys.stdout.write("LOADING SURFACE VARIANCE {} out of {} images\r".format(frame, nframe))
		sys.stdout.flush()

		auv1, auv2 = np.load('{}/ACOEFF/{}_{}_{}_{}_{}_R_INTCOEFF.npy'.format(directory, model.lower(), qm, n0, int(1./phi + 0.5), frame), mmap_mode='r')

		av_auv1_2 += auv1**2 / nframe
		av_auv2_2 += auv2**2 / nframe

		mean_auv1[frame] += auv1[len(auv1)/2]
		mean_auv2[frame] += auv2[len(auv2)/2]

	pos = (np.mean(mean_auv1) - np.mean(mean_auv2)) / 2. 

	Z = np.linspace(-(DIM[2]/2+pos), -pos, nlayers)

	print ""

	if model.upper() not in ['ARGON', 'DMSO']: 
		experiment = EXPERIMENT[model.upper()]

		psi_exp = experiment[4]
		delta_exp = experiment[5]

		print "EXPERIMENTAL ELLIPICITY"
		exp_ellipicity = []
		for i, delta in enumerate(delta_exp):
			index = psi_exp[i].argmin()
			exp_ellipicity.append(np.tan(psi_exp[i][index] * degree) * np.sin(delta[index] * degree) * 1E4)
			print exp_ellipicity[-1]

		index = experiment[1].argmin()
		print "AVERAGE = {}   {} ({})\n".format(np.tan(experiment[1][index] * degree) * np.sin(experiment[2][index] * degree)*1E4, np.mean(exp_ellipicity), sp.stats.sem(exp_ellipicity))

	POL = ['p', 's']
	d_list = np.ones(nlayers) * lslice
      	d_list[0] = np.inf
        d_list[-1] = np.inf

	no_array, ne_array = load_theoretical(directory, model, nslice, a_type, DIM, nframe, ellip_angles)

	ellipicity = np.zeros(len(no_array))

	ow_ellip = bool(raw_input("OVERWRITE ELLIPSOMETRY RESULTS? (Y/N): ").upper() == 'Y')

        for i, no in enumerate(no_array):
		signal = []
		for t, theta in enumerate(ellip_angles):
			r_ps = []
			for p, pol in enumerate(POL):
				if pol == 's': n = no
				else: n = ne_array[i][t]
				r, t = ellips(n, theta, lam_vac, d_list, nlayers, pol, 0)
				r_ps.append(r)
			signal.append(r_ps[0] / r_ps[1])

		Psi = [np.arctan(abs(ratio)) / degree for ratio in signal]
		Delta = [np.angle(-ratio, deg=True) + 180  for ratio in signal]

		plt.figure(0, figsize=(fig_x,fig_y))
		#fig = plt.figure(0, figsize=(fig_x+5,fig_y+5))
                #ax = fig.gca(projection='3d')
		plt.plot(Z, no)

		plt.figure(1, figsize=(fig_x,fig_y))
		plt.plot(ellip_angles / degree, Psi)

		plt.figure(2, figsize=(fig_x,fig_y))
		plt.plot(ellip_angles / degree, Delta)

		ellipicity[i] = np.imag(signal[np.array(Psi).argmin()])*1E4 

	print "\n{:10s} | {:10s} | {:10s} | {:10s} | {:10s} | {:10s} | {:10s} | {:10s} ".format("qm", "lambda", "lambda (nm)", "var", "int_ep", "eff_ep1", "eff_ep2", "eff_ep3")
        print "-" * 14 * 9

	print "{:10d} & {:10s} & {:10s} & {:10.3f} & {:10.2f} & {:10.2f} & {:10.2f} & {:10.2f} \\\\".format(0, '', '', 0, ellipicity[0], ellipicity[1], ellipicity[1], ellipicity[1])

	plt.figure(0, figsize=(fig_x,fig_y))
	plt.xlabel(r'z Coordinate (\AA)')
	plt.ylabel(r'n (a.u.)')
	plt.legend(loc=2)
	plt.axis([-10, 15, 1, 1.8])
	plt.savefig('{}/{}_{}_{}_n_profile.png'.format(groot, model.lower(), nslice, nframe))
	plt.savefig('{}/{}_{}_{}_n_profile.pdf'.format(groot, model.lower(), nslice, nframe))

	plt.figure(1, figsize=(fig_x,fig_y))
	if model.upper() not in ['ARGON', 'DMSO']:
		#for i in xrange(len(experiment[3])):plt.scatter(experiment[3][i], experiment[4][i], s=15, c='black', marker='x')
		#plt.plot(experiment[0], experiment[1], linestyle='dashed', c='black')
		for i in xrange(len(experiment[3])):plt.plot(experiment[3][i], experiment[4][i], c='black', marker='x', linestyle='dotted')
	plt.xlabel(r'$\theta_i$ ($^\circ$)')
	plt.ylabel(r'$\Psi$')
	plt.axis([start_angle, end_angle, 0, 2.0])
	plt.legend(loc=4)
	plt.savefig('{}/{}_{}_{}_amplitude.png'.format(groot, model.lower(), nslice, nframe))
	plt.savefig('{}/{}_{}_{}_amplitude.pdf'.format(groot, model.lower(), nslice, nframe))

	plt.figure(2, figsize=(fig_x,fig_y))
	if model.upper() not in ['ARGON', 'DMSO']:
		#for i in xrange(len(experiment[3])):plt.scatter(experiment[3][i], experiment[5][i], s=15, c='black', marker='x')
		for i in xrange(len(experiment[3])):plt.plot(experiment[3][i], experiment[5][i], c='black', marker='x', linestyle='dotted')
		plt.plot(experiment[0], experiment[2], linestyle='dashed', c='black')
	plt.xlabel(r'$\theta_i$ ($^\circ$)')
	plt.ylabel(r'$\Delta$ ($^\circ$)')
	plt.axis([start_angle, end_angle, 0, 360])
	plt.legend(loc=2)
	plt.savefig('{}/{}_{}_{}_delta.png'.format(groot, model.lower(), nslice, nframe))
	plt.savefig('{}/{}_{}_{}_delta.pdf'.format(groot, model.lower(), nslice, nframe))

        plt.close('all')

	q_max = 2 * np.pi / mol_sigma
	q_min = 2 * np.pi / np.sqrt(DIM[0] * DIM[1])

	COLOUR = ['b', 'g', 'r', 'cyan']
        LEGEND = [r'$\tilde{n}(z)$', r'$\hat{n}_1(z)$', r'$\hat{n}_2(z)$', r'$\hat{n}_3(z)$', r'$\hat{n}_4(z)$']

	surf_ep1 = np.zeros((len(QM), 2))
	surf_pos = (np.mean(mean_auv1)-np.mean(mean_auv2))/2
	fixed_surf_index = int(2 * (DIM[2]/2+surf_pos) / DIM[2] * nlayers + 0.5)

	rho_qm = np.zeros((len(QM), 4))
	lambda_m = q_max / (q_min * np.array(QM)) 

	if not os.path.exists('{}/ELLIPSOMETRY'.format(directory)): os.mkdir('{}/ELLIPSOMETRY'.format(directory))

	no_array, ne_array, exx_array, ezz_array = load_theoretical_ism(directory, model, nslice, a_type, DIM, qm, n0, phi, nframe, ellip_angles, surf_pos)

	n_model = len(no_array)

	for j, qu in enumerate(QM):

		file_name_ellip = '{}_{}_{}_{}_{}_{}_{}_R'.format(model.lower(), nslice, a_type, qm, qu, int(1/phi+0.5), n_angle)

		Delta1 = (ut.sum_auv_2(av_auv1_2, qm, qu) - np.mean(mean_auv1)**2)
                Delta2 = (ut.sum_auv_2(av_auv2_2, qm, qu) - np.mean(mean_auv2)**2)

                cap_var = np.mean([Delta1, Delta2])

		surf_index = fixed_surf_index
                searching = True

                while searching:
                        if no_array[0][qu][surf_index+1] > no_array[0][qu][surf_index]: surf_index += 1
                        else: searching = False

		B_angle = []

		ellipicity = np.zeros(n_model)
                drude_ellip = np.zeros(n_model)
                rough_ellip = np.zeros(n_model)

                qxi2_sum = ellip_capillary((av_auv1_2 + av_auv2_2)/2, qm, qu, DIM)

		if os.path.exists('{}/ELLIPSOMETRY/{}_PSI.npy'.format(directory, file_name_ellip)) and not ow_ellip:
			with open('{}/ELLIPSOMETRY/{}_PSI.npy'.format(directory, file_name_ellip), 'r') as infile:
				psi_spec = np.load(infile)
			with open('{}/ELLIPSOMETRY/{}_DELTA.npy'.format(directory, file_name_ellip), 'r') as infile:
                                delta_spec = np.load(infile)

		else:
			#sys.stdout.write("RUNNING ELLIPSOMETRY EXPERIMENT nm = {} qm = {} slices\r".format(nm, qm))
                	#sys.stdout.flush()
			
			psi_spec = np.zeros((n_model, n_angle))
			delta_spec = np.zeros((n_model, n_angle))
			rho_spec = np.zeros((n_model, n_angle))

			VAR = [cap_var] * n_model

			for i in xrange(n_model):
				no = no_array[i][qu]
				signal = []
				for t, theta in enumerate(ellip_angles):
					r_ps = []

					for p, pol in enumerate(POL):
						if pol == 's': n = no
						else: n = ne_array[i][qu][t]			
						r, t = ellips(n, theta, lam_vac, d_list, nlayers, pol, cap_var)
						r_ps.append(r)

					signal.append(r_ps[0] / r_ps[1])

				Psi = [np.arctan(abs(ratio)) / degree for ratio in signal]
				Delta = [np.angle(-ratio, deg=True) + 180  for ratio in signal]
				Rho = np.imag(np.array(signal)) * 1E4

				psi_spec[i] += np.array(Psi)
				delta_spec[i] += np.array(Delta)

			with open('{}/ELLIPSOMETRY/{}_PSI.npy'.format(directory, file_name_ellip), 'w') as outfile:
                                np.save(outfile, psi_spec)
                        with open('{}/ELLIPSOMETRY/{}_DELTA.npy'.format(directory, file_name_ellip), 'w') as outfile:
                                np.save(outfile, delta_spec)

		for i in xrange(n_model):

			B_angle.append(np.array(psi_spec[i]).argmin())

			#plt.figure(0, figsize=(fig_x,fig_y))
			#plt.plot(Z, no_array[i][qu], label=LEGEND[i], c=COLOUR[i])
			#plt.plot(Z, ne_array[i][qu][B_angle[i]], label=LEGEND[i], c=COLOUR[i], linestyle='dashed')
			#plt.plot([Z[surf_index], Z[surf_index]], [0, 2], c='black', linestyle='dashed')

			#plt.figure(1, figsize=(fig_x,fig_y))
			#plt.plot(ellip_angles / degree, psi_spec[i], label=LEGEND[i])

			#plt.figure(2, figsize=(fig_x,fig_y))
			#plt.plot(ellip_angles / degree, delta_spec[i], label=LEGEND[i])

			#plt.show()
			#plt.savefig('{}/DATA/ellipsometry_{}_delta.png'.format(directory, model.lower()))

			ellipicity[i] = np.tan(psi_spec[i][B_angle[i]] * degree) * np.sin(delta_spec[i][B_angle[i]] * degree) * 1E4
			drude_ellip[i] = 1E4 * np.pi / lam_vac * np.sqrt(exx_array[i][qu][0]+exx_array[i][qu][-1])/(exx_array[i][qu][0]-exx_array[i][qu][-1]) * lslice * np.sum([exx_array[i][qu][l] + exx_array[i][qu][0]*exx_array[i][qu][-1] / ezz_array[i][qu][l] - exx_array[i][qu][0] - exx_array[i][qu][-1] for l in range(nlayers)])
			rough_ellip[i] = - 1E4 * 3./2 * np.pi / lam_vac * (exx_array[i][qu][0]-exx_array[i][qu][-1])**2/(exx_array[i][qu][0]+exx_array[i][qu][-1]) * qxi2_sum

			if qu % 1 == 0:
				if i == 1 or not np.isnan(ellipicity[0]):
                                	fig = plt.figure(10+i, figsize=(fig_x+5,fig_y+5))
                                	ax = fig.gca(projection='3d')
                                	ax.plot(ellip_angles / degree, np.ones(n_angle) * qu, delta_spec[i], c='b')

                                	fig = plt.figure(20+i, figsize=(fig_x+5,fig_y+5))
                                	ax = fig.gca(projection='3d')
                                	ax.plot(ellip_angles / degree, np.ones(n_angle) * qu, psi_spec[i], c='r')

			#print "surface n = {:.5f}   bulk n = {:.5f}   dn = {:.5f} ({:.2%})".format(no[surf_index], no[-1], no[surf_index]- n[-1], (no[surf_index] - no[-1]) / no[-1])
			#print "Ellipsometry direction = {}  Ellipicity = {}\n".format(np.sign(Delta[-1] - Delta[0]), np.imag(signal[B_angle[i]]))
		rho_qm[j] += ellipicity
		if not np.isnan(ellipicity).any(): print "{:10d} & {:10.3f} & {:10.3f} & {:10.3f} & {:10.2f} & {:10.2f} & {:10.2f} & {:10.2f} \\\\".format(qm, q_max / (q_min * qu), q_max / (10 * q_min * qu) * mol_sigma, cap_var, ellipicity[0], ellipicity[1], ellipicity[2], ellipicity[3])
		else: print "{:10d} & {:10.3f} & {:10.3f} & {:10.3f} & {:10s} & {:10.2f} & {:10s} & {:10s} \\\\".format(qm, q_max / (q_min * qu), q_max / (10 * q_min * qu) * mol_sigma, cap_var, '', ellipicity[1], '', '')
		surf_ep1[j] += np.array([no_array[0][qu][surf_index]**2, no_array[0][qu][-1]**2])
		"""
		"THEORETICAL ELLIPICITY"

		exx_array = np.array(no_array)**2

		for i, exx in enumerate(exx_array):
			ezz = np.array(ne_array[i][B_angle[i]])**2
			ellip = np.array([exx[i] + (exx[0] * exx[-1]) / ezz[i] - exx[-1] - exx[0] for i in range(nslice/2)]) * np.pi * np.sqrt((exx[0] + exx[-1])) / (lam_vac * (exx[0] - exx[-1]))
			plt.figure(3, figsize=(fig_x,fig_y))
			plt.plot(Z, exx)
			plt.figure(4, figsize=(fig_x,fig_y))
			plt.plot(Z, ellip)
			print np.sum(ellip) * lslice
		#"""

		"""
		plt.figure(0, figsize=(fig_x,fig_y))
		plt.xlabel(r'z Coordinate (\AA)')
		plt.ylabel(r'n (a.u.)')
		plt.legend(loc=2)
		plt.axis([-10, 15, 1, 1.8])
		plt.savefig('{}/{}_{}_{}_{}_{}_{}_n_profile.png'.format(groot, model.lower(), nslice, nm, qm, int(1/phi+0.5), nframe))
		plt.savefig('{}/{}_{}_{}_{}_{}_{}_n_profile.pdf'.format(groot, model.lower(), nslice, nm, qm, int(1/phi+0.5), nframe))
		plt.close(0)

		plt.figure(1, figsize=(fig_x,fig_y))
		if model.upper() not in ['ARGON', 'DMSO']: 
			#for i in xrange(len(experiment[3])):plt.scatter(experiment[3][i], experiment[4][i], s=15, c='black', marker='x')
			#plt.plot(experiment[0], experiment[1], linestyle='dashed', c='black')
			for i in xrange(len(experiment[3])):plt.plot(experiment[3][i], experiment[4][i], c='black', marker='x', linestyle='dotted')
		plt.xlabel(r'$\theta_i$ ($^\circ$)')
		plt.ylabel(r'$\Psi$')
		plt.axis([start_angle, end_angle, 0, 2.0])
		plt.legend(loc=4)
		plt.savefig('{}/{}_{}_{}_{}_{}_{}_amplitude.png'.format(groot, model.lower(), nslice, nm, qm, int(1/phi+0.5), nframe))
		plt.savefig('{}/{}_{}_{}_{}_{}_{}_amplitude.pdf'.format(groot, model.lower(), nslice, nm, qm, int(1/phi+0.5), nframe))
		plt.close(1)

		plt.figure(2, figsize=(fig_x,fig_y))
		if model.upper() not in ['ARGON', 'DMSO']: 
			#for i in xrange(len(experiment[3])):plt.scatter(experiment[3][i], experiment[5][i], s=15, c='black', marker='x')
			for i in xrange(len(experiment[3])):plt.plot(experiment[3][i], experiment[5][i], c='black', marker='x', linestyle='dotted')
			#plt.plot(experiment[0], experiment[2], linestyle='dashed', c='black')
		plt.xlabel(r'$\theta_i$ ($^\circ$)')
		plt.ylabel(r'$\Delta$ ($^\circ$)')
		plt.axis([start_angle, end_angle, 0, 360])
		plt.legend(loc=2)
		plt.savefig('{}/{}_{}_{}_{}_{}_{}_delta.png'.format(groot, model.lower(), nslice, nm, qm, int(1/phi+0.5), nframe))
		plt.savefig('{}/{}_{}_{}_{}_{}_{}_delta.pdf'.format(groot, model.lower(), nslice, nm, qm, int(1/phi+0.5), nframe))
		plt.close(2)
		"""

        print "{:10s} | {:10s} | {:10s} | {:10s} | {:10s} | {:10s}".format("qm", "lambda", "var", "diff surf no1", "diff surf ep1", "percentage")
        print "-" * 14 * 5

	figure_name = '{}_{}_{}_{}'.format(model.lower(), qm, int(1/phi+0.5), nframe)

	rho_qm = np.transpose(rho_qm)
	var_xi = np.zeros(len(QM))

	index = np.min(np.argwhere(np.isnan(rho_qm[0])))

	plt.figure(2, figsize=(fig_x,fig_y))
	fig, ax = plt.subplots(figsize=(fig_x,fig_y))
	plt.plot(lambda_m[:index], rho_qm[0][:index], label=r'$\tilde{\epsilon}$')
	plt.plot(lambda_m, rho_qm[1], label=r'$\hat{\epsilon}_1$')
	plt.plot(lambda_m[:index], rho_qm[2][:index], label=r'$\hat{\epsilon}_2$')
	plt.plot(lambda_m[:index], rho_qm[3][:index], label=r'$\hat{\epsilon}_3$')
	exp_mean = np.array([np.mean(exp_ellipicity), np.mean(exp_ellipicity)])
	exp_std = np.std(exp_ellipicity)
	plt.plot([0, lambda_m[0]], np.zeros(2), c='black', lw=1.0)
	plt.plot([0, lambda_m[0]], exp_mean, c='black', linestyle='dashed', label='Experimental', lw=2.0)
	plt.fill_between([0, lambda_m[0]], exp_mean-exp_std, exp_mean+exp_std, alpha=0.15, edgecolor='black', facecolor='black')
	plt.axis([1, qm/2, -50, 50])
	plt.xlabel(r'$\lambda_m$ ($\sigma_m^{-1}$)')
	plt.ylabel(r'$\bar{\rho}$')
	plt.legend(loc=4)

	axins = plt.axes([0,0,1,1])
	ip = InsetPosition(ax, [0.08,0.7,0.7,0.25])
	axins.set_axes_locator(ip)
	#axins = inset_axes(ax, width='35%', height=3.5, loc=2)
	plt.plot(lambda_m[:index], rho_qm[0][:index])
        plt.plot(lambda_m, rho_qm[1])
        plt.plot(lambda_m[:index], rho_qm[2][:index])
        plt.plot(lambda_m[:index], rho_qm[3][:index])
	axins.set_xlim(1, 8)
	axins.set_ylim(rho_qm[1][0]-0.5, rho_qm[1][0]+0.5)
	mark_inset(ax, axins, loc1=3, loc2=4, fc="none", ec="0.5")	

	plt.savefig('{}/{}_rho_lam.png'.format(groot, figure_name))
        plt.savefig('{}/{}_rho_lam.pdf'.format(groot, figure_name))
		
	plt.figure(3, figsize=(fig_x,fig_y))
        plt.plot(var_xi[:index], rho_qm[0][:index], label=r'$\tilde{\epsilon}$')
        plt.plot(var_xi, rho_qm[1], label=r'$\hat{\epsilon}_1$')
        plt.plot(var_xi[:index], rho_qm[2][:index], label=r'$\hat{\epsilon}_2$')
	plt.plot(var_xi[:index], rho_qm[3][:index], label=r'$\hat{\epsilon}_3$')
	plt.axis([np.min(var_xi)-0.1, np.max(var_xi)+0.1, -5, 10])
        plt.xlabel(r'$\Delta(a_{\mu\nu})$ (\AA)')
        plt.ylabel(r'$\bar{\rho}$')
        plt.legend(loc=2)
        plt.savefig('{}/{}_rho_var.png'.format(groot, figure_name))
        plt.savefig('{}/{}_rho_var.pdf'.format(groot, figure_name))

	for i in xrange(len(no_array)):
		fig = plt.figure(10+i, figsize=(fig_x+5,fig_y+5))
		ax = fig.gca(projection='3d')
		for j in xrange(len(experiment[3])): ax.plot(experiment[3][j], np.ones(len(experiment[3][j])) * (qm+1), experiment[5][j], c='black', marker='x', linestyle='dotted')
		ax.set_xlabel(r'$\theta_i$ (\AA)', labelpad=lnsp)
		ax.set_xlim3d(start_angle, end_angle)
		ax.set_zlabel(r'$\Delta$ ($^\circ$)', labelpad=lnsp)
		ax.set_zlim3d(0, 360)
		ax.set_ylabel(r'$q_u$', labelpad=lnsp)
		ax.set_ylim3d(1, qm+1)
		plt.savefig('{}/{}_delta_spec_{}.png'.format(groot, figure_name, i))
		plt.savefig('{}/{}_delta_spec_{}.pdf'.format(groot, figure_name, i))

		fig = plt.figure(20+i, figsize=(fig_x+5,fig_y+5))
                ax = fig.gca(projection='3d')
                for j in xrange(len(experiment[3])): ax.plot(experiment[3][j], np.ones(len(experiment[3][j])) * (qm+1), experiment[4][j], c='black', marker='x', linestyle='dotted')
                ax.set_xlabel(r'$\theta_i$ (\AA)', labelpad=lnsp)
                ax.set_xlim3d(start_angle, end_angle)
                ax.set_zlabel(r'$\Psi$ ($^\circ$)', labelpad=lnsp)
                ax.set_zlim3d(0, 2.0)
                ax.set_ylabel(r'$q_u$', labelpad=lnsp)
                ax.set_ylim3d(0, qm+1)
                plt.savefig('{}/{}_psi_spec_{}.png'.format(groot, figure_name, i))
                plt.savefig('{}/{}_psi_spec_{}.pdf'.format(groot, figure_name, i))
	plt.close('all')	
   
