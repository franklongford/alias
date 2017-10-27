"""
*************** DENSITY ANALYSIS MODULE *******************

Atomic, molecular and mass density profile of simulation 
trajectories.

density_array[0] 		= mass count
density_array[1:n_atom_types]   = atom count
density_array[-1] 		= mol count

***************************************************************
Created 24/11/2016 by Frank Longford

Contributors: Frank Longford

Last modified 24/04/2017 by Frank Longford
"""

import numpy as np
import scipy as sp
import time, sys, os

from scipy import constants as con
from scipy.optimize import curve_fit

import utilities as ut
#import matplotlib.pyplot as plt

def count(directory, model, csize, nslice, nsite, natom, AT, M, DIM, COM, frame, ow_count):
	
	file_name = '{}_{}_{}'.format(model.lower(), nslice, frame)

	if os.path.exists('{}/DEN/{}_COUNT.txt'.format(directory, file_name)): ut.convert_txt_npy('{}/DEN/{}_COUNT'.format(directory, file_name))
	if os.path.exists('{}/DEN/{}_COUNT.npy'.format(directory, file_name)) and not ow_count:
		try:
			with file('{}/DEN/{}_{}_{}_COUNT.npy'.format(directory, model.lower(), nslice, frame)) as infile:
				count_array = np.load(infile)
		except IndexError: ow_count = True
	else: ow_count = True

	if ow_count:

		atom_types = list(set(AT))
		n_atom_types = len(atom_types)
	
		count_array = [np.zeros(nslice) for n in range(2 + n_atom_types)]

		xat, yat, zat = ut.read_atom_positions(directory, model, csize, frame)
		xmol, ymol, zmol = ut.read_mol_positions(directory, model, csize, frame)
		xR, yR, zR = COM[frame]

		for n in xrange(natom):
			m = n % nsite
			at_type = AT[m]

			try:
				z = (zat[n] - zR + 0.5 * DIM[2])
			except:
				print n, natom, len(zat) 
				sys.exit()
			index_at = int(z * nslice / DIM[2]) % nslice

			count_array[0][index_at] += M[m]
			count_array[1 + atom_types.index(at_type)][index_at] += 1

			if m == 0:
				z = (zmol[n/nsite] - zR + 0.5 * DIM[2])
				index_mol = int(z * nslice / DIM[2]) % nslice
				count_array[-1][index_mol] += 1

		with file('{}/DEN/{}_{}_{}_COUNT.npy'.format(directory, model.lower(), nslice, frame), 'w') as outfile:
			np.save(outfile, (count_array))		

	return count_array



def density_profile(directory, model, csize, suffix, nframe, natom, nmol, nsite, AT, M, COM, DIM, nslice, ow_count):
	"Saves atom, mol and mass profiles as well as parameters for a tanh mol density function, fitted to ntraj number of trajectory snapshots" 

	print "\nCALCULATING DENSITY {}".format(directory)

	atom_types = list(set(AT))
	n_atom_types = len(atom_types)

	av_density_array = [np.zeros(nslice) for n in range(2 + n_atom_types)]

	avpl = []
	avpv = []
	avden = []
	avz0 = []
	
	Z1 = np.linspace(0, DIM[2], nslice)
	Z2 = np.linspace(-1/2.*DIM[2], 1/2.*DIM[2], nslice)

	vslice = DIM[0] * DIM[1] * DIM[2] / nslice
	Acm = 1E-8

	for frame in xrange(nframe):
		sys.stdout.write("PROCESSING {} out of {} FRAMES\r".format(frame, nframe) )
		sys.stdout.flush()
		
		count_array = count(directory, model, csize, nslice, nsite, natom, AT, M, DIM, COM, frame, ow_count)
		
		for i in xrange(2 + n_atom_types): av_density_array[i] += count_array[i] / (nframe * vslice)

	print "\n"

	av_density_array[0] = av_density_array[0] / (con.N_A * Acm**3)

	param, _ = curve_fit(ut.den_func, Z1, av_density_array[0], [1., 0., DIM[2]/2., DIM[2]/4., 2.])
	param = np.absolute(param)

	print "WRITING TO FILE..."

	file_name = '{}_{}_{}'.format(model.lower(), nslice, nframe)

	with file('{}/DEN/{}_DEN.npy'.format(directory, file_name), 'w') as outfile:
		np.save(outfile, (av_density_array))
	with file('{}/DEN/{}_PAR.npy'.format(directory, file_name), 'w') as outfile:
		np.save(outfile, param)

	print "{} {} {} COMPLETE\n".format(directory, model.upper(), csize)


