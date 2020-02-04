"""
*************** UTILITIES MODULE *******************

Generic functions to be used across multiple programs
within ALIAS.

***********************************************************
Created 24/11/2016 by Frank Longford

Contributors: Frank Longford

Last modified 27/2/2018 by Frank Longford
"""

import numpy as np
import subprocess, os, sys, pickle, tables

from scipy import stats
from scipy.signal import convolve
import scipy.constants as con

import mdtraj as md

from alias.version import __version__

SQRT2 = np.sqrt(2.)
SQRTPI = np.sqrt(np.pi)


def numpy_remove(list1, list2):
	"""
	Deletes overlapping elements of list2 from list1
	"""

	return np.delete(list1, np.where(np.isin(list1, list2)))


def make_checkfile(checkfile_name):
	"""
	Creates checkfile for analysis, storing key paramtere
	"""

	checkfile = {}
	with open(checkfile_name + '.pkl', 'wb') as outfile:
		pickle.dump(checkfile, outfile, pickle.HIGHEST_PROTOCOL)


def read_checkfile(checkfile_name):
	"""
	Reads checkfile to lookup stored key paramters
	"""

	with open(checkfile_name + '.pkl', 'rb') as infile:
		return pickle.load(infile)


def update_checkfile(checkfile_name, symb, obj):
	"""
	Updates checkfile parameter

	Parameters
	----------
	checkfile_name:  str
			Checkfile path + name
	symb:  str
			Key for checkfile dictionary of object obj
	obj:
			Parameter to be saved

	Returns
	-------
	checkfile:  dict
			Dictionary of key parameters
	"""

	with open(checkfile_name + '.pkl', 'rb') as infile:
		checkfile = pickle.load(infile)
	checkfile[symb] = obj

	with open(checkfile_name + '.pkl', 'wb') as outfile:
		pickle.dump(checkfile, outfile, pickle.HIGHEST_PROTOCOL)
	return checkfile


def get_sim_param(traj_file, top_file):
	"""
	Returns selected parameters of input trajectory and topology file using mdtraj
	
	Parameters
	----------
	top_dir:  str
			Directory of topology file
	traj_dir:  str
			Directory of trajectory file
	traj_file:  str
			Trajectory file name
	top_file:  str
			Topology file name

	Returns
	-------
	traj:  mdtraj obj
			Mdtraj trajectory object
	mol:  str, list
			List of residue types in simulation cell
	nframe:  int
			Number of frames sampled in traj_file
	dim:  float, array_like; shape=(3):
			Simulation cell dimensions (angstroms)
	"""

	traj = md.load_frame(traj_file, 0, top=top_file)
	mol = list(set([molecule.name for molecule in traj.topology.residues]))	

	return traj, mol


def molecules(xat, yat, zat, nmol, nsite, mol_M, mol_com):
	"""
	Returns XYZ arrays of molecular positions"

	Parameters
	----------

	xat:  float, array_like; shape=(natom)
		Coordinates of atoms in x dimension
	yat:  float, array_like; shape=(natom)
		Coordinates of atoms in y dimension
	zat:  float, array_like; shape=(natom)
		Coordinates of atoms in z dimension
	nmol:  int
		Number of molecules in simulation
	nsite:  int
		Number of atomic sites per molecule
	mol_M:  float, array_like; shape=(natom)
		Masses of atomic sites in g mol-1
	mol_com:
		Mode of calculation: if 'COM', centre of mass is used, otherwise atomic site index is used

	Returns
	-------

	xmol:  float, array_like; shape=(nmol)
		Coordinates of molecules in x dimension
	ymol:  float, array_like; shape=(nmol)
		Coordinates of molecules in y dimension
	zmol:  float, array_like; shape=(nmol)
		Coordinates of molecules in z dimension

	"""
	if mol_com == 'COM':
		"USE COM of MOLECULE AS MOLECULAR POSITION"
		xmol = np.sum(np.reshape(xat * mol_M, (nmol, nsite)), axis=1) * nmol / mol_M.sum()
		ymol = np.sum(np.reshape(yat * mol_M, (nmol, nsite)), axis=1) * nmol / mol_M.sum()
		zmol = np.sum(np.reshape(zat * mol_M, (nmol, nsite)), axis=1) * nmol / mol_M.sum()
	
	elif len(mol_com) > 1:
		"USE COM of GROUP OF ATOMS WITHIN MOLECULE MOLECULAR POSITION"
		mol_list = np.arange(nmol) * nsite
		mol_list = mol_list.repeat(len(mol_com)) + np.tile(mol_com, nmol)

		xmol = np.sum(np.reshape(xat[mol_list] * mol_M[mol_list], 
				(nmol, len(mol_com))), axis=1) * nmol / mol_M[mol_list].sum()
		ymol = np.sum(np.reshape(yat[mol_list] * mol_M[mol_list], 
				(nmol, len(mol_com))), axis=1) * nmol / mol_M[mol_list].sum()
		zmol = np.sum(np.reshape(zat[mol_list] * mol_M[mol_list], 
				(nmol, len(mol_com))), axis=1) * nmol / mol_M[mol_list].sum()
	
	elif len(mol_com) == 1:
		"USE SINGLE ATOM AS MOLECULAR POSITION"
		mol_list = np.arange(nmol) * nsite + int(mol_com[0])
		xmol = xat[mol_list]
		ymol = yat[mol_list]
		zmol = zat[mol_list]

	return xmol, ymol, zmol


def orientation(traj, AT):
	"""
	Calculates orientational unit vector for lipid models, based on vector between phosphorus group
	and carbon backbone.
	"""

	if len(AT) == 134:
		P_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'P')]
		C1_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'C218')]
		C2_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'C316')]

	elif len(AT) == 138:
		P_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'P')]
		C1_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'C218')]
		C2_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'C318')]
	else:
		P_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'PO4')]
		C1_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'C4A')]
		C2_atoms = [atom.index for atom in traj.topology.atoms if (atom.name == 'C4B')]
		
	XYZ = traj.xyz * 10
	dim = traj.unitcell_lengths * 10
	u_vectors = np.zeros((XYZ.shape[0], len(P_atoms), 3))

	for j in range(XYZ.shape[0]):
		midpoint = (XYZ[j][C1_atoms] + XYZ[j][C2_atoms]) / 2 
		vector = XYZ[j][P_atoms] - midpoint
		for i, l in enumerate(dim[j]): vector[:, i] -= l * np.array(2 * vector[:, i] / l, dtype=int)
		u_vectors[j] = unit_vector(vector)

	return u_vectors


def load_npy(file_path, frames=[]):
	"""
	load_npy(file_path, frames=[])

	General purpose algorithm to load an array from a npy file

	Parameters
	----------

	file_path:  str
		Path name of npy file
	frames:  int, list (optional)
		Trajectory frames to load

	Returns
	-------

	array:  array_like (float);
		Data array to be loaded
	"""

	if len(frames) == 0:
		array = np.load(file_path + '.npy', mmap_mode='r')
	else:
		array = np.load(file_path + '.npy', mmap_mode='r')[frames]

	return array


def make_mol_com(traj_file, top_file, directory, file_name, natom, nmol, AT, at_index, nsite, mol_M, sys_M, mol_com, nframe=0):
	"""
	make_mol_com(traj, directory, file_name, natom, nmol, at_index, nframe, dim, nsite, M, mol_com)

	Generates molecular positions and centre of mass for each frame

	Parameters
	----------

	traj:  mdtraj obj
		Mdtraj trajectory object
	directory:  str
		File path of directory of alias analysis.
	file_name:  str
		File name of trajectory being analysed
	natom:  int
		Number of atoms in simulation
	nmol:  int
		Number of molecules in simulation
	at_index:  int, array_like; shape=(nsite*nmol)
		Indicies of atoms that are in molecules selected to determine intrinsic surface
	nframe:  int
		Number of frames in simulation trajectory
	nsite:  int
		Number of atomic sites in molecule
	M:  float, array_like; shape=(nsite)
		Masses of atomic sites in molecule
	mol_com:
		Mode of calculation: if 'COM', centre of mass is used, otherwise atomic site index is used

	"""
	print("\n-----------CREATING POSITIONAL FILES------------\n")
	
	pos_dir = directory + 'pos/'
	if not os.path.exists(pos_dir): os.mkdir(pos_dir)

	file_name_pos = file_name + '_{}'.format(nframe)

	if not os.path.exists(pos_dir + file_name_pos + '_zvec.npy'):

		dim = np.zeros((0, 3))
		xmol = np.zeros((0, nmol))
		ymol = np.zeros((0, nmol))
		zmol = np.zeros((0, nmol))
		COM = np.zeros((0, 3))
		zvec = np.zeros((0, nmol))

		mol_M = np.array(mol_M * nmol)
		sys_M = np.array(sys_M)

		#XYZ = np.moveaxis(traj.xyz, 1, 2) * 10

		chunk = 500

		#for frame in xrange(nframe):
		for i, traj in enumerate(md.iterload(traj_file, chunk=chunk, top=top_file)):

			lengths = np.array(traj.unitcell_lengths)
			zvec = np.concatenate((zvec, orientation(traj, AT)[:,:,2]))
			chunk_index = np.arange(i*chunk, i*chunk + traj.n_frames)

			XYZ = np.moveaxis(traj.xyz, 1, 2) * 10

			for j, frame in enumerate(chunk_index):
				sys.stdout.write("PROCESSING IMAGE {} \r".format(frame))
				sys.stdout.flush()

				COM = np.concatenate((COM, [traj.xyz[j].astype('float64').T.dot(sys_M / sys_M.sum()) * 10]))
				dim = np.concatenate((dim, [lengths[j] * 10]))

				xat = XYZ[j][0][at_index]
				yat = XYZ[j][1][at_index]
				zat = XYZ[j][2][at_index]

				if nsite > 1: 
					xyz_mol = molecules(xat, yat, zat, nmol, nsite, mol_M, mol_com)
					xmol = np.concatenate((xmol, [xyz_mol[0]]))
					ymol = np.concatenate((ymol, [xyz_mol[1]]))
					zmol = np.concatenate((zmol, [xyz_mol[2]]))

				else: 
					xmol = np.concatenate((xmol, [xat]))
					ymol = np.concatenate((ymol, [yat]))
					zmol = np.concatenate((zmol, [zat]))

		nframe = zmol.shape[0]
		file_name_pos = file_name + '_{}'.format(nframe)

		print('\nSAVING OUTPUT MOLECULAR POSITION FILES\n')

		np.save(pos_dir + file_name_pos + '_dim.npy', dim)
		np.save(pos_dir + file_name_pos + '_xmol.npy', xmol)
		np.save(pos_dir + file_name_pos + '_ymol.npy', ymol)
		np.save(pos_dir + file_name_pos + '_zmol.npy', zmol)
		np.save(pos_dir + file_name_pos + '_com.npy', COM)
		np.save(pos_dir + file_name_pos + '_zvec.npy', zvec)

	return nframe
	

def bubble_sort(array, key):
	"""
	bubble_sort(array, key)

	Sorts array and key by order of elements of key
	"""

	for passnum in range(len(array)-1, 0, -1):
		for i in range(passnum):
			if key[i] > key[i+1]:
				temp = array[i]
				array[i] = array[i+1]
				array[i+1] = temp

				temp = key[i]
				key[i] = key[i+1]
				key[i+1] = temp


def unit_vector(vector, axis=-1):
	"""
	unit_vector(vector, axis=-1)

	Returns unit vector of vector
	"""

	vector = np.array(vector)
	magnitude_2 = np.sum(vector.T**2, axis=axis)
	u_vector = np.sqrt(vector**2 / magnitude_2) * np.sign(vector)

	return u_vector


def linear(x, m, c):
	return m * x + c


def gaussian(x, mean, std):
	return np.exp(-(x-mean)**2 / (2 * std**2)) / (SQRT2 * std * SQRTPI)


def gaussian_convolution(array, centre, delta, dim, nslice):
	"""
	Convolution of distributions 'arrays' using a normal probability distribution with mean=centres and variance=deltas

	Parameters
	----------
	array:  float, array_like; shape=(nslice)
		Array to convolute
	centre: float
		Mean value for normal probability distribution
	delta: float	
		Variance for normal probability distribution
	dim:  float, array_like; shape=(3)
		XYZ dimensions of simulation cell
	nslice: int
		Number of bins in density histogram along axis normal to surface

	Returns
	-------
	conv_array:  float, array_like; shape=(nslice)
		Convoluted array
	"""

	std = np.sqrt(delta)
	lslice = dim[2] / nslice
	length = int(std / lslice) * 10
	ZG = np.arange(0, dim[2], lslice)

	index = nslice / 8
	array = np.roll(array, -index)

	gaussian_array = gaussian(ZG, centre+ZG[index], std) * lslice
	conv_array = convolve(array, gaussian_array, mode='same')

	"""
	import matplotlib.pyplot as plt
	plt.figure(100)
	plt.plot(ZG, gaussian_array)
	plt.plot(ZG, array)
	plt.plot(ZG, conv_array)
	plt.show()
	#"""

	return conv_array


def make_earray(file_name, arrays, atom, sizes):
	"""
	General purpose algorithm to create an empty earray

	Parameters
	----------
	file_name:  str
		Name of file
	arrays:  str, list
		List of references for arrays in data table
	atom:  type
		Type of data in earray
	sizes:  int, tuple
		Shape of arrays in data set
	"""

	with tables.open_file(file_name, 'w') as outfile:
		for i, array in enumerate(arrays):
			outfile.create_earray(outfile.root, array, atom, sizes[i])


def make_hdf5(file_path, shape, datatype):
	"""
	General purpose algorithm to create an empty hdf5 file

	Parameters
	----------
	file_path:  str
		Path name of hdf5 file
	shape:  int, tuple
		Shape of dataset in hdf5 file
	datatype:  type
		Data type of dataset
	"""

	shape = (0,) + shape

	make_earray(file_path + '.hdf5', ['dataset'], datatype, [shape])


def load_hdf5(file_path, frame='all'):
	"""
	General purpose algorithm to load an array from a hdf5 file

	Parameters
	----------
	file_path:  str
		Path name of hdf5 file
	frame:  int (optional)
		Trajectory frame to load

	Returns
	-------
	array:  array_like (float);
		Data array to be loaded, same shape as object 'dataset' in hdf5 file
	"""

	with tables.open_file(file_path + '.hdf5', 'r') as infile:
		if frame == 'all': array = infile.root.dataset[:]
		else: array = infile.root.dataset[frame]

	return array


def save_hdf5(file_path, array, frame, mode='a'):
	"""
	General purpose algorithm to save an array from a single frame a hdf5 file

	Parameters
	----------
	file_path:  str
		Path name of hdf5 file
	array:  array_like (float);
		Data array to be saved, must be same shape as object 'dataset' in hdf5 file
	frame:  int
		Trajectory frame to save
	mode:  str (optional)
		Option to append 'a' to hdf5 file or overwrite 'r+' existing data	
	"""

	if not mode: return

	shape = (1,) + array.shape

	with tables.open_file(file_path + '.hdf5', mode) as outfile:
		assert outfile.root.dataset.shape[1:] == shape[1:]
		if mode.lower() == 'a':
			write_array = np.zeros(shape)
			write_array[0] = array
			outfile.root.dataset.append(write_array)
		elif mode.lower() == 'r+':
			outfile.root.dataset[frame] = array


def shape_check_hdf5(file_path):
	"""
	General purpose algorithm to check the shape the dataset in a hdf5 file 

	Parameters
	----------
	file_path:  str
		Path name of hdf5 file

	Returns
	-------
	shape_hdf5:  int, tuple
		Shape of object dataset in hdf5 file
	"""

	with tables.open_file(file_path + '.hdf5', 'r') as infile:
		shape_hdf5 = infile.root.dataset.shape

	return shape_hdf5


def view_surface(coeff, pivot, qm, qu, xmol, ymol, zmol, nxy, dim):

	import matplotlib
	#matplotlib.use('Agg')
	import matplotlib.pyplot as plt
	import matplotlib.animation as anim
	from mpl_toolkits.mplot3d import Axes3D
	
	from .intrinsic_sampling_method import check_uv, xi, check_pbc

	zmol = check_pbc(xmol, ymol, zmol, pivot, dim)

	X = np.linspace(0, dim[0], nxy)
	Y = np.linspace(0, dim[1], nxy)

	vcheck = np.vectorize(check_uv)

	n_waves = 2 * qm + 1
	u_array = np.array(np.arange(n_waves**2) / n_waves, dtype=int) - qm
	v_array = np.array(np.arange(n_waves**2) % n_waves, dtype=int) - qm
	wave_check = (u_array >= -qu) * (u_array <= qu) * (v_array >= -qu) * (v_array <= qu)
	Delta = 1. / 4 * np.sum(coeff**2 * wave_check * vcheck(u_array, v_array))

	surface = np.zeros((2, nxy, nxy))
	
	for i, x in enumerate(X): 
		for j in range(2): surface[j][i] += xi(np.ones(nxy) * x, Y, coeff[j], qm, qu, dim)

	surface = np.moveaxis(surface, 1, 2)

	fig = plt.figure(0, figsize=(15,15))
	ax = fig.gca(projection='3d')
	ax.set_xlabel(r'$x$ (\AA)')
	ax.set_ylabel(r'$y$ (\AA)')
	ax.set_zlabel(r'$z$ (\AA)')
	ax.set_xlim3d(0, dim[0])
	ax.set_ylim3d(0, dim[1])
	ax.set_zlim3d(-dim[2]/2, dim[2]/2)
	X_grid, Y_grid = np.meshgrid(X, Y)		

	def update(frame):
		ax.clear()		
		ax.plot_wireframe(X_grid, Y_grid, surface[0], color='r')
		ax.scatter(xmol[pivot[0]], ymol[pivot[0]], zmol[pivot[0]], color='b')
		ax.plot_wireframe(X_grid, Y_grid, surface[1], color='r')
		ax.scatter(xmol[pivot[1]], ymol[pivot[1]], zmol[pivot[1]], color='g')

	a = anim.FuncAnimation(fig, update, frames=1, repeat=False)
	#plt.savefig('plot_{}_{}.png'.format(len(pivot[0]), len(pivot[1])))
	plt.show()


def print_alias():

	print(' '+ '_' * 43)
	print("|                   __ __             ____  |")
	print("|     /\     |        |       /\     /      |")
	print("|    /  \    |        |      /  \    \___   |")
	print("|   /___ \   |        |     /___ \       \  |")
	print("|  /      \  |____  __|__  /      \  ____/  |")
	print(f"|'+ '_' * 43 + '|' + '  v{__version__}")
	print("\n    Air-Liquid Interface Analysis Suite \n")