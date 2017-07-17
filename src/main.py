"""
*************** MAIN INTERFACE MODULE *******************

Main program, ALIAS: Air-Liquid Interface Analysis Suite

***********************************************************
Created 24/11/2016 by Frank Longford

Contributors: Frank Longford

Last modified 24/11/2016 by Frank Longford
"""

import numpy as np
import os

import utilities as ut

print ' '+ '_' * 43
print "|                   __ __             ____  |"
print "|     /\     |        |       /\     /      |" 
print "|    /  \    |        |      /  \    \___   |"
print "|   /___ \   |        |     /___ \       \  |"
print "|  /      \  |____  __|__  /      \  ____/  |"
print '|'+ '_' * 43 + '|' + '  v0.2'
print ""
print "    Air-Liquid Interface Analysis Suite"
print ""

model = raw_input("Which model?\n\nArgon\nSPCE\nTIP3P\nTIP4P2005\nAMOEBA\nMethanol\nEthanol\nDMSO\n\n")

nsite, AT, Q, M, LJ = ut.get_param(model)

if model.upper() in ['METHANOL', 'ETHANOL', 'DMSO', 'AMOEBA']: folder = 'SURFACE'
else: folder = 'SURFACE_2'

suffix = 'surface'

if model.upper() in ['METHANOL', 'ETHANOL', 'DMSO']:
	a_type = 'calc'
	com = 'COM'
else: 
	com = '0'
	if model.upper() == 'AMOEBA': a_type = 'ame'
	else: a_type = 'exp'

T = int(raw_input("Temperature: (K) "))
cutoff = int(raw_input("Cutoff: (A) "))
func = raw_input("Function:\nTest or Slab? (T, S): ")

if model.upper() in['ARGON', 'METHANOL', 'ETHANOL', 'DMSO']: root = '/data/fl7g13/AMBER/{}/T_{}_K/CUT_{}_A'.format(model.upper(), T, cutoff)
else: root = '/data/fl7g13/AMBER/WATER/{}/T_{}_K/CUT_{}_A'.format(model.upper(), T, cutoff)

if func.upper() == 'T':
	TYPE = raw_input("Width (W), Area (A) or Cubic (C) variation: ")
	force = raw_input("VDW Force corrections? (Y/N): ")

	root = '{}/{}_TEST'.format(root, TYPE.upper())

	if force.upper() == 'Y': folder = 'SURFACE_2'
	else: folder = 'SURFACE' 

	suffix = 'surface'
	csize = 50

	if model.upper() == 'ARGON':
		if folder.upper() == 'SURFACE_2':
			if TYPE.upper() == 'W': 
				nfolder = 60
				sfolder = 11 
			elif TYPE.upper() == 'A': 
				nfolder = 25
				sfolder = 4
			elif TYPE.upper() == 'C': 
				nfolder = 22
				sfolder = 0
		else:
			if TYPE.upper() == 'W': 
				nfolder = 60
				sfolder = 11
			elif TYPE.upper() == 'C': 
				nfolder = 7
				csize = 30

	if model.upper() == 'TIP4P2005':
		if TYPE.upper() == 'W': 
			nfolder = 40
			sfolder = 11 
		if TYPE.upper() == 'A': nfolder = 25
		if TYPE.upper() == 'C':
		        nfolder = 2
		        csize = 35
		if T != 298: nfolder = 1	

	if model.upper() in ['SPCE', 'TIP3P']:
		if TYPE.upper() == 'W':
			nfolder = 40
			sfolder = 11

	print ""
	build = bool(raw_input("Make input files or Analyse?").upper() == 'Y')

	if build: pass
	else:

		TASK = raw_input("What task to perform?\nD  = Density Profile\nIS = Intrinsic Surface Profiling\nO  = Orientational Profile\nE  = Dielectric and Refractive Index.\nT  = Thermodynamics\nEL = Ellipsometry module\nG  = Print Graphs\n")
		print ""

		if TASK.upper() == 'D':

			ow_all =  bool(raw_input("OVERWRITE ALL DENISTY? (Y/N): ").upper() == 'Y')
			sigma = np.max(LJ[1])
			lslice = 0.05 * sigma

			for i in xrange(sfolder, nfolder):
				root_ = '{}/{}_{}'.format(root, TYPE.upper(), i)
				directory = '{}/{}'.format(root_, folder.upper())
		
				ow_den = True
				ow_count = False

				if os.path.exists('{}/DATA/parameters.txt'.format(directory)) and not ow_all:
					print "LOADING {}/DATA/parameters.txt".format(directory)
					with file('{}/DATA/parameters.txt'.format(directory), 'r') as infile:
						_, _, ntraj, _, _, dim_Z = np.loadtxt(infile)

					ntraj = int(ntraj)
					nslice = int(dim_Z / lslice)

					if os.path.exists('{}/DATA/DEN/{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, ntraj)) and not ow_all:
						print "FILE FOUND '{}/DATA/DEN/{}_{}_{}_{}_DEN.txt".format(directory, model.lower(), csize, nslice, ntraj)
						ow_den = bool(raw_input("OVERWRITE? (Y/N): ").upper() == 'Y')
						if ow_den: ow_count = bool(raw_input("OVERWRITE COUNT? (Y/N): ").upper() == 'Y')

				if ow_den or ow_all:
					import density as den

					print '{}/{}/{}_{}_{}.nc'.format(root_, folder.upper(), model.lower(), csize, suffix)
					traj = ut.load_nc(root_, folder, model, csize, suffix)

					if not os.path.exists("{}/DATA".format(directory)): os.mkdir("{}/DATA".format(directory))

					natom = int(traj.n_atoms)
					nmol = int(traj.n_residues)
					ntraj = int(traj.n_frames)
					DIM = np.array(traj.unitcell_lengths[0]) * 10

					with file('{}/DATA/parameters.txt'.format(directory), 'w') as outfile:
						np.savetxt(outfile, [natom, nmol, ntraj, DIM[0], DIM[1], DIM[2]])

					nslice = int(DIM[2] / lslice)

					if not os.path.exists("{}/DATA/DEN".format(directory)): os.mkdir("{}/DATA/DEN".format(directory))
						
					if ow_all: den.density_thermo(traj, directory, model, csize, suffix, ntraj, natom, nmol, nsite, AT, M, com, DIM, nslice, ow_all)
					else: den.density_thermo(traj, directory, model, csize, suffix, ntraj, natom, nmol, nsite, AT, M, com, DIM, nslice, ow_count)

				print ""

		elif TASK.upper() == 'T':

			import thermodynamics as thermo

			rc = float(cutoff)

			"Conversion of length and surface tension units"
			if model.upper() == 'ARGON':
				LJ[0] = LJ[0] * 4.184
				e_constant = 1 / LJ[0]
				st_constant = ((LJ[1]*1E-10)**2) * con.N_A * 1E-6 / LJ[0]
				l_constant = 1 / LJ[1]
				T = 85
				com = 0
			else: 
				LJ[0] = LJ[0] * 4.184
				e_constant = 1.
				st_constant = 1.
				l_constant = 1E-10
				T = 298

			ow_area = bool(raw_input("OVERWRITE INTRINSIC SURFACE AREA? (Y/N): ").upper() == 'Y')
			ow_ntb = bool(raw_input("OVERWRITE SURFACE TENSION ERROR? (Y/N): ").upper() == 'Y')
			ow_est = bool(raw_input("OVERWRITE AVERAGE ENERGY AND TENSION? (Y/N): ").upper() == 'Y')
			(ENERGY, ENERGY_ERR, TEMP, TEMP_ERR, TENSION, TENSION_ERR, VAR_TENSION, N_RANGE, A_RANGE, AN_RANGE, Z_RANGE, DEN) = thermo.energy_tension(
				root, model, suffix, TYPE, folder, sfolder, nfolder, T, rc, LJ, csize, e_constant, l_constant, st_constant, com, ow_area, ow_ntb, ow_est)

		elif TASK.upper() == 'G':
			import graphs
			graphs.print_graphs_thermodynamics(root, model, nsite, AT, Q, M, LJ, T, cutoff, csize, folder, suffix)


elif func.upper() == 'S':

	import sys
	import mdtraj as md
	import density as den
	import intrinsic_surface as surf
	import orientational as ori
	import dielectric as die
	import ellipsometry as ellips
	import graphs
	from scipy import constants as con
	import matplotlib.pyplot as plt

	TYPE = 'SLAB'

	if model.upper() == 'AMOEBA': 
		csize = 50
		root = '/data/fl7g13/OpenMM/WATER/{}/T_{}_K/CUT_{}_A/{}'.format(model.upper(), T, cutoff, TYPE.upper())
	elif model.upper() == 'DMSO':
		csize = 120
		root = '{}/{}'.format(root, TYPE.upper())	
	else:
		csize = 80
		root = '{}/{}'.format(root, TYPE.upper())

	sigma = np.max(LJ[1])

	if model.upper() not in ['SPCE', 'AMOEBA']:
		directory = '{}/CUBE'.format(root)
		if not os.path.exists("{}/DATA".format(directory)): os.mkdir("{}/DATA".format(directory))

		rad_dist = bool(raw_input("PERFORM RADIAL DISTRIBUTION? (Y/N): ").upper() == 'Y')

		if rad_dist:
			print "\n-------------CUBIC RADIAL DISTRIBUTION-----------\n"
	
			if not os.path.exists("{}/DATA/DEN".format(directory)): os.mkdir("{}/DATA/DEN".format(directory))

			traj = ut.load_nc(root, 'CUBE', model, csize, 'cube')

			natom = int(traj.n_atoms)
			nmol = int(traj.n_residues)
			ntraj = int(traj.n_frames)
			DIM = np.array(traj.unitcell_lengths[0]) * 10

			nimage = 10#ntraj

			lslice = 0.01
			max_r = np.min(DIM) / 2.
			nslice = int(max_r / lslice)

			ow_all = False
			ow_count = False

			if os.path.exists('{}/DATA/DEN/{}_{}_{}_{}_RDEN.txt'.format(directory, model.lower(), csize, nslice, nimage)) and not ow_all:
				print "FILE FOUND '{}/DATA/DEN/{}_{}_{}_{}_RDEN.txt".format(directory, model.lower(), csize, nslice, nimage)
				if bool(raw_input("OVERWRITE? (Y/N): ").upper() == 'Y'):
					ow_count = bool(raw_input("OVERWRITE COUNT? (Y/N): ").upper() == 'Y')
					den.radial_dist(traj, directory, model, nimage, max_r, lslice, nslice, natom, nmol, nsite, AT, M, csize, DIM, com, ow_count)	
			else: den.radial_dist(traj, directory, model, nimage, max_r, lslice, nslice, natom, nmol, nsite, AT, M, csize, DIM, com, ow_all)

			with open('{}/DATA/DEN/{}_{}_{}_{}_RDEN.txt'.format(directory, model.lower(), csize, nslice, nimage), 'r') as infile:
				av_density_array = np.loadtxt(infile)

			mol_sigma = 2**(1./6) * av_density_array[0].argmax() * lslice

			plt.plot(np.linspace(0, max_r ,nslice), av_density_array[0])
			plt.show()

			print "molecular sigma = {}".format(mol_sigma)
	
	directory = '{}/{}'.format(root, folder.upper())
	if not os.path.exists("{}/DATA".format(directory)): os.mkdir("{}/DATA".format(directory))

	print "\n----------BUILDING SURFACE POSITIONAL ARRAYS-----------\n"

	if not os.path.exists("{}/DATA/POS".format(directory)): os.mkdir("{}/DATA/POS".format(directory))

	ow_pos = bool(raw_input("OVERWRITE AT MOL POSITIONS? (Y/N): ").upper() == 'Y')

	if os.path.exists('{}/DATA/parameters.txt'.format(directory)) and not ow_pos:
		DIM = np.zeros(3)
		with file('{}/DATA/parameters.txt'.format(directory), 'r') as infile:
			natom, nmol, ntraj, DIM[0], DIM[1], DIM[2] = np.loadtxt(infile)
		natom = int(natom)
		nmol = int(nmol)
		ntraj = int(ntraj)

		print 'LOADING PARAMETER AND COM FILES'
		with file('{}/DATA/POS/{}_{}_{}_COM.txt'.format(directory, model.lower(), csize, ntraj), 'r') as infile:
			COM = np.loadtxt(infile)

	else:
		print '{}/{}/{}_{}_{}.nc'.format(root, folder.upper(), model.lower(), csize, suffix)
		traj = ut.load_nc(root, folder, model, csize, suffix)

		natom = int(traj.n_atoms)
		nmol = int(traj.n_residues)
		ntraj = int(traj.n_frames)
		DIM = np.array(traj.unitcell_lengths[0]) * 10

		with file('{}/DATA/parameters.txt'.format(directory), 'w') as outfile:
			np.savetxt(outfile, [natom, nmol, ntraj, DIM[0], DIM[1], DIM[2]])

		XAT = np.zeros((ntraj, natom))
		YAT = np.zeros((ntraj, natom))
		ZAT = np.zeros((ntraj, natom))
		XMOL = np.zeros((ntraj, nmol))
		YMOL = np.zeros((ntraj, nmol))
		ZMOL = np.zeros((ntraj, nmol))
		COM = np.zeros((ntraj, 3))

		for image in xrange(ntraj):
			sys.stdout.write("PROCESSING {} out of {} IMAGES\r".format(image, ntraj) )
			sys.stdout.flush()

			ZYX = np.rot90(traj.xyz[image])
			ZAT[image] += ZYX[0] * 10
			YAT[image] += ZYX[1] * 10
			XAT[image] += ZYX[2] * 10

			XMOL[image], YMOL[image], ZMOL[image] = ut.molecules(XAT[image], YAT[image], ZAT[image], nsite, M, com=com)
			COM[image] = ut.centre_mass(XAT[image], YAT[image], ZAT[image], nsite, M)

			with file('{}/DATA/POS/{}_{}_{}_XAT.txt'.format(directory, model.lower(), csize, image), 'w') as outfile:
				np.savetxt(outfile, XAT[image], fmt='%-12.6f')
			with file('{}/DATA/POS/{}_{}_{}_YAT.txt'.format(directory, model.lower(), csize, image), 'w') as outfile:
				np.savetxt(outfile, YAT[image], fmt='%-12.6f')
			with file('{}/DATA/POS/{}_{}_{}_ZAT.txt'.format(directory, model.lower(), csize, image), 'w') as outfile:
				np.savetxt(outfile, ZAT[image], fmt='%-12.6f')
			with file('{}/DATA/POS/{}_{}_{}_XMOL.txt'.format(directory, model.lower(), csize, image), 'w') as outfile:
				np.savetxt(outfile, XMOL[image], fmt='%-12.6f')
			with file('{}/DATA/POS/{}_{}_{}_YMOL.txt'.format(directory, model.lower(), csize, image), 'w') as outfile:
				np.savetxt(outfile, YMOL[image], fmt='%-12.6f')
			with file('{}/DATA/POS/{}_{}_{}_ZMOL.txt'.format(directory, model.lower(), csize, image), 'w') as outfile:
				np.savetxt(outfile, ZMOL[image], fmt='%-12.6f')
		print 'SAVING OUTPUT FILES COM\n'
		with file('{}/DATA/POS/{}_{}_{}_COM.txt'.format(directory, model.lower(), csize, ntraj), 'w') as outfile:
			np.savetxt(outfile, COM, fmt='%-12.6f')

	lslice = 0.05 * sigma
	nslice = int(DIM[2] / lslice)
	vlim = 3
	ncube = 3

	if model.upper() in ['TIP4P2005', 'ARGON', 'AMOEBA']: mol_sigma = sigma
	elif model.upper() == 'METHANOL': mol_sigma = 3.83
	elif model.upper() == 'ETHANOL': mol_sigma = 4.57
	elif model.upper() == 'DMSO': mol_sigma = 5.72

	nm = int((DIM[0] + DIM[1]) / (2 * mol_sigma))

	nimage = ntraj

	print "\n-----------STARTING DENSITY PROFILE------------\n"
	
	if not os.path.exists("{}/DATA/DEN".format(directory)): os.mkdir("{}/DATA/DEN".format(directory))

	ow_all = False
	ow_count = False

	if os.path.exists('{}/DATA/DEN/{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, nimage)) and not ow_all:
		print "FILE FOUND '{}/DATA/DEN/{}_{}_{}_{}_DEN.txt".format(directory, model.lower(), csize, nslice, nimage)
		if bool(raw_input("OVERWRITE? (Y/N): ").upper() == 'Y'):
			ow_count = bool(raw_input("OVERWRITE COUNT? (Y/N): ").upper() == 'Y')
			den.density_profile(directory, model, csize, suffix, nimage, natom, nmol, nsite, AT, M, COM, DIM, nslice, ow_count)	
	else: den.density_profile(directory, model, csize, suffix, nimage, natom, nmol, nsite, AT, M, COM, DIM, nslice, ow_all)
	
	print "\n------STARTING INTRINSIC DENSITY PROFILE-------\n"

	ow_all = False
	ow_coeff = False
	ow_curve = False
	ow_count = False
	ow_wden = False

	if not os.path.exists("{}/DATA/INTDEN".format(directory)): os.mkdir("{}/DATA/INTDEN".format(directory))
	if not os.path.exists("{}/DATA/INTPOS".format(directory)): os.mkdir("{}/DATA/INTPOS".format(directory))

	if os.path.exists('{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt'.format(directory, model.lower(), csize, nslice, nm, nimage)) and not ow_all:
		print "FILE FOUND '{}/DATA/INTDEN/{}_{}_{}_{}_{}_DEN.txt".format(directory, model.lower(), csize, nslice, nm, nimage)
		if bool(raw_input("OVERWRITE? (Y/N): ").upper() == 'Y'):
			ow_coeff = bool(raw_input("OVERWRITE ACOEFF? (Y/N): ").upper() == 'Y')
			#ow_curve = bool(raw_input("OVERWRITE CURVE? (Y/N): ").upper() == 'Y')
			ow_count = bool(raw_input("OVERWRITE COUNT? (Y/N): ").upper() == 'Y')
			ow_wden = bool(raw_input("OVERWRITE WDEN? (Y/N): ").upper() == 'Y')		
			surf.intrinsic_profile(directory, model, csize, suffix, nimage, natom, nmol, nsite, AT, M, mol_sigma, COM, DIM, nslice, ncube, nm, vlim, ow_coeff, ow_curve, ow_count, ow_wden)
	else: surf.intrinsic_profile(directory, model, csize, suffix, nimage, natom, nmol, nsite, AT, M, mol_sigma, COM, DIM, nslice, ncube, nm, vlim, ow_all, ow_all, ow_all, ow_all)

	#graphs.print_graphs_density(directory, model, nsite, AT, nslice, nm, cutoff, csize, folder, suffix, nimage, DIM)

	if model.upper() != 'ARGON':

		ow_all = False
		ow_angles = False

		print "\n--------STARTING ORIENTATIONAL PROFILE--------\n"

		if not os.path.exists("{}/DATA/EULER".format(directory)): os.mkdir("{}/DATA/EULER".format(directory))
		if not os.path.exists("{}/DATA/INTEULER".format(directory)): os.mkdir("{}/DATA/INTEULER".format(directory))

		if os.path.exists('{}/DATA/EULER/{}_{}_{}_{}_{}_EUL.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage)) and not ow_all:
			print 'FILE FOUND {}/DATA/EULER/{}_{}_{}_{}_{}_EUL.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage)
			if bool(raw_input("OVERWRITE? (Y/N): ").upper() == 'Y'):  
				ow_angles = bool(raw_input("OVERWRITE ANGLES? (Y/N): ").upper() == 'Y')
				ow_polar = bool(raw_input("OVERWRITE POLARISABILITY? (Y/N): ").upper() == 'Y') 
				ori.euler_profile(directory, nimage, nslice, nmol, model, csize, suffix, AT, Q, M, LJ, COM, DIM, nsite, a_type, nm, ow_angles, ow_polar)
		else: ori.euler_profile(directory, nimage, nslice, nmol, model, csize, suffix, AT, Q, M, LJ, COM, DIM, nsite, a_type, nm, ow_all, ow_all)

	#graphs.print_graphs_orientational(directory, model, nsite, AT, nslice, nm, a_type, cutoff, csize, folder, suffix, nimage, DIM)

	ow_all = False
	ow_ecount = False
	ow_acount = False

	print "\n-------STARTING DIELECTRIC PROFILE--------\n"

	if not os.path.exists("{}/DATA/DIELEC".format(directory)): os.mkdir("{}/DATA/DIELEC".format(directory))
	if not os.path.exists("{}/DATA/INTDIELEC".format(directory)): os.mkdir("{}/DATA/INTDIELEC".format(directory))
	if not os.path.exists("{}/DATA/ELLIP".format(directory)): os.mkdir("{}/DATA/ELLIP".format(directory))

	if os.path.exists('{}/DATA/DIELEC/{}_{}_{}_{}_{}_DIE.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage)) and not ow_all:
		print 'FILE FOUND {}/DATA/DIELEC/{}_{}_{}_{}_{}_DIE.txt'.format(directory, model.lower(), csize, nslice, a_type, nimage)
		if bool(raw_input("OVERWRITE? (Y/N): ").upper() == 'Y'):   
			#ow_ecount = bool(raw_input("OVERWRITE ECOUNT? (Y/N): ").upper() == 'Y')
			#ow_acount = bool(raw_input("OVERWRITE ACOUNT? (Y/N): ").upper() == 'Y') 
			die.dielectric_refractive_index(directory, model, csize, AT, sigma, nslice, nimage, a_type, nm, DIM, ow_ecount, ow_acount)
	else: die.dielectric_refractive_index(directory, model, csize, AT, sigma, nslice, nimage, a_type, nm, DIM, ow_all, ow_acount)

	#graphs.print_graphs_dielectric(directory, model, nsite, AT, nslice, nm, a_type, cutoff, csize, folder, suffix, nimage, DIM)

	print "\n-------STARTING ELLIPSOMETRY PREDICTIONS--------\n"

	ellips.transfer_matrix(directory, model, csize, AT, sigma, nslice, nimage, a_type, nm, DIM, cutoff)

