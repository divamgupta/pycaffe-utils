## @package my_sqlite
#  Wrapper around sqlite3 to ease reading and writing
#  in pythonic form.

import sqlite3
import uuid
import collections as co
import pickle
import copy
from os import path as osp

def type2str(typ):
	if typ in [float]:
		return '%f'
	elif typ in [bool, int]:
		return '%d'
	elif typ in [str, type(None)]:
		return '%s'
	else:
		raise Exception('Type %s not recognized' % typ)

def type2SqType(typ):
	if typ in [type(None)]:
		return 'NULL'
	elif typ in [int, long]:
		return 'INTEGER'
	elif typ in [str]:
		return 'TEXT'
	elif typ in [float]:	
		return 'REAL'
	else:
		raise Exception('Type %s not recognized' % typ)
	

class SqDb(object):
	'''
		Wrapper class which makes it easy to manipulate SQLite3 objects using
		pythonic interface of passing in dicts. 
		
		Each new row is assigned a uuid stored in the field _mysqlid, this field
		cannot be added by the user. 

		If fields have None as the value then it is regarded as NULL in SQL palance.
		This has a side-effect that if dicts are passed in a way that a certian
		variable always has None value it is never recoreded in the database. 	
	'''
	#Make a Db
	def __init__(self, name):
		self.c_  = sqlite3.connect(name)
		#Create a helper file
		helpFile = name + '-helper.pkl'
		if osp.exists(helpFile):
			data = pickle.load(open(helpFile, 'rb'))
		self.colNames_ = co.OrderedDict()
		tableNames     = self.get_table_names()
		if not 'table1' in tableNames:
			self.create_table(tableName='table1')

	def close(self):
		self.c_.close()

	def execute(self, cmd):
		print (cmd)	
		self.c_.execute(cmd)
		#self.c_.commit()	
	
	def get_table_names(self):
		cmd    = "SELECT name FROM sqlite_master WHERE type='table'"
		cs     = self.c_.execute(cmd)	
		tNames = []
		for n in  cs.fetchall():
			tNames.append(n[0])
		return tNames	

	#get the column and value pairs
	def get_column_value_pair(self, vals):
		cl, vl = '', ''
		for k, v in vals.iteritems():
			cl = cl + '%s,' % k
			if type(v) is str:
				vl = vl + ('"%s",' % v)
			else: 
				vl = vl + ('%s,' % type2str(type(v))) % v
		cl = cl[:-1]
		vl = vl[:-1]
		return cl, vl

	#get the sql index condition
	def get_sql_index_condition(self, vals):
		idxStr = ''
		for k, v in vals.iteritems():
			if type(v) == str:
				s = ('%s = "%s"' % (k, type2str(type(v)))) % v
			else:	
				s = ('%s = %s' % (k, type2str(type(v)))) % v
			idxStr = idxStr + ' AND %s' % s
		idxStr = idxStr[5:]
		return idxStr	
	
	#get rid of all None values in vals
	def _process_vals(self, vals):
		assert not '_mysqlid' in vals.keys()
		vals = copy.deepcopy(vals)
		delKeys = []
		for k, v in vals.iteritems():
			if v is None:
				delKeys.append(k)
		for k in delKeys:
			del vals[k]
		return vals 

	#Create table
	def create_table(self, tableName='table1'):
		tableNames = self.get_table_names()
		assert tableName not in tableNames,'Table %s exists' % tableName
		cmd  = ('CREATE TABLE %s(_mysqlid TEXT)' % tableName)
		self.execute(cmd)

	#Add to the db
	def add(self, vals, tableName='table1'):
		vals    = self._process_vals(vals)
		entry   = self.get(vals, tableName)
		if len(entry) > 0:
			raise Exception ('Entry already exists, cannot add')
		vals['_mysqlid'] = str(uuid.uuid1())
		newCols = self._check_columns(vals, tableName)
		co, vl = self.get_column_value_pair(vals) 
		cmd=('INSERT INTO %s ({}) VALUES ({})' % tableName).format(co, vl)
		self.execute(cmd)	

	#Get matching entried
	def get(self, vals, tableName='table1'):
		vals    = self._process_vals(vals)
		newCols = self._check_columns(vals, tableName)
		if newCols: 
			return []
		indexStr = self.get_sql_index_condition(vals)  
		cmd = 'SELECT * FROM %s WHERE %s' % (tableName, indexStr)
		self.c_.row_factory = sqlite3.Row
		cs  = self.c_.execute(cmd)
		rows = cs.fetchall()
		out  = []
		for r in rows:
			out.append(dict(r))
		return out	

	#fetch the entry if it exists or create a new one
	def fetch(self, vals={}, tableName='table1'):
		vals    = self._process_vals(vals)
		newCols = self._check_columns(vals, tableName)
		if newCols: 
			self.add(vals, tableName)
		out = self.get(vals, tableName)
		if len(out) > 0:
			return out
		else:
			self.add(vals, tableName)
			return self.get(vals, tableName)	
	
	#Check columns
	def _check_columns(self, vals={}, tableName='table1'):
		newCols = False
		colNames = self.get_column_names()
		if not set(vals.keys()).issubset(set(colNames)):
			newCols = True
			for k in vals.keys():
				if k in colNames:
					continue
				self._add_column(k, type2SqType(type(vals[k])), tableName)	
		return newCols		


	#Add a column to the table
	def _add_column(self, colName, colType, tableName='table1'):	
		colNames = self.get_column_names()
		assert colName not in colNames, '%s column already exists' % colName
		cmd = 'ALTER TABLE %s ADD COLUMN %s %s' % (tableName, colName, colType)
		self.execute(cmd)

	#Get columns names
	def get_column_names(self, tableName='table1'):
		#return self.colNames_[tableName].keys()
		return self._get_column_names_from_db(tableName)
	
	#Get the names of columns from the db
	def _get_column_names_from_db(self, tableName='table1'):
		cs    = self.c_.execute('SELECT * FROM %s' % tableName) 
		names = [description[0] for description in cs.description]	
		return names
		
