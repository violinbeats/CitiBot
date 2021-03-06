from station import Station
from provider import Provider
from collections import deque
from sklearn.externals import joblib
import numpy as np
import pandas as pd
import random

def main():
	# using real station id from training set - stations with far apart number of visits
	s1 = Station(387)
	s2 = Station(521)
	s3 = Station(293)
	s4 = Station(127)
	s5 = Station(83)

	stations = [s1, s2, s3, s4, s5]
	provider = Provider()

	models = joblib.load("research/models/singleGBMs.pkl")

	tomorrow = 1 # initialize as Monday
	print('############################################################################')
	print('                       Start On-demand Marketplace!')
	print('############################################################################')
	print('Current usage:')
	print('------------------------------------')
	print('Station 1:', s1.usage)
	print('Station 2:', s2.usage)
	print('Station 3:', s3.usage)
	print('Station 4:', s4.usage)
	print('Station 5:', s5.usage)

	print('\nCiti Bike Info:')
	print('------------------------------------')
	print('Available Budget:', Station._budgetLeft)
	percentage = sum([s.inService for s in stations]) / len(stations)
	print('% stations in service:', "{0:.0%}".format(percentage))

	print('\nProvider Info:')
	print('------------------------------------')
	print('Available Inventory:', Provider._inventory)
	print('Profit:', Provider._profit)
	# print('Pricing:')
	# print('Level 1 costs', ''.join(['$',str(Provider._levelList[1][0])]), 'and takes', Provider._levelList[1][1], 'days')
	# print('Level 2 costs', ''.join(['$',str(Provider._levelList[2][0])]), 'and takes', Provider._levelList[2][1], 'days')
	# print('Level 3 costs', ''.join(['$',str(Provider._levelList[3][0])]), 'and takes', Provider._levelList[3][1], 'days')

	print('\nDemand prediction for next 7 days:')
	print('------------------------------------')
	
	# predict station demand for the next 7 days at each station using its own pre-trained model
	demandsNext = deque() # use queue to update rolling demands

	for day in range(1,8):
		features = []
		demands = []
		indices = range(len(stations))

		# generate this day's weather forecast
		high, low, rain, snow = genWeather()
		
		# predict demand for each station for the next day
		for station, index in zip(stations, indices):
			# generate feature vector for prediction model
			features.append(genFeature(day, station.id, high, low, rain, snow))
			pred = models[index].predict(features[-1])
			if pred < 0:
				demands.append(0)
			else:
				demands.append(int(pred[0]))
		
		demandsNext.append(demands)

	print(demandsNext)
	cumulatedDemand = list(np.array(demandsNext).sum(axis=0))
	print("Cumulated:", cumulatedDemand)

	print("\nMaintenance prediction for each station next week:")
	print("------------------------------------")
	# which station may need service next week 
	maxUsage = s1.maxUsage # masusage are the same for all stations
	mayNeedService = []
	for station, demand in zip(stations, cumulatedDemand):
		bound = station.usage + demand
		if bound > maxUsage:
			mayNeedService.append("Might break down!!")
		elif bound > maxUsage / 2:
			mayNeedService.append("May request service.")
		else:
			mayNeedService.append("Good for now.")
	print(mayNeedService)
	# how many? 
	numNeedService = sum([1 if x != "Good for now." else 0 for x in mayNeedService ])
	print("Number of stations that might need service:", numNeedService)

	# select levels based on objective: max availability, max profit, ...
	Station._requestLevels = selectLevels(numNeedService, avail = 0, profit = 0, cost = 1)

	input("\nPress Enter to continue...\n")
	# next day to predict is Monday
	nextDay = 1

	# TODO above code might be repeated unnecessarily
	while True:

		# generate station visits for the day
		actualVisits = []
		for station, demand in zip(stations, demands):
			if station.inService == 0:
				# cannot visit the station if it's not in operation
				actualVisits.append(0)
			else:
				actualVisit = int(max(random.uniform(demand*0.9,demand*1.1), 0))
				station.visit(actualVisit)
				actualVisits.append(actualVisit)
		
		print('############################################################################')
		print('Current station usage:')
		print('------------------------------------')
		print('Station 1:', s1.usage)
		print('Station 2:', s2.usage)
		print('Station 3:', s3.usage)
		print('Station 4:', s4.usage)
		print('Station 5:', s5.usage)

		print('\nCiti Bike Info:')
		print('------------------------------------')

		percentage = sum([s.inService for s in stations]) / len(stations)

		Station._score += percentage

		# update day of week and reset when beyond Sunday
		nextDay += 1
		if nextDay == 8:
			nextDay = 1
			Station._budgetLeft = Station._budget # renew weekly budget
			totalProfit = Provider._profit
			Provider._profit = 0 # reset weekly budget

			# print objective: avg availability for the past week
			avgScore = Station._score / 7
			print('Station 7-day average availability:', "{:.0%}".format(avgScore))			
			Station._score = 0

		print('Available Budget:', station._budgetLeft)
		print('% stations in service:', "{:.0%}".format(percentage))

		print('\nProvider Info:')
		print('------------------------------------')
		if nextDay == 1:
			print('Weekly profit:', "${0}".format(totalProfit))
		print('Available Inventory:', Provider._inventory)
		print('Profit:', Provider._profit)	
		# print('Pricing:')
		# print('Level 1 costs', ''.join(['$',str(Provider._levelList[1][0])]), 'and takes', Provider._levelList[1][1], 'days')
		# print('Level 2 costs', ''.join(['$',str(Provider._levelList[2][0])]), 'and takes', Provider._levelList[2][1], 'days')
		# print('Level 3 costs', ''.join(['$',str(Provider._levelList[3][0])]), 'and takes', Provider._levelList[3][1], 'days')

		# get next day's weather features
		high, low, rain, snow = genWeather()

		# predict demand for each station for the next day		
		features = []
		demands = []
		currentUsage = [] # create a current usage list to compare with future demand and decide service level
		for station, index in zip(stations, indices):
			# create current usage list
			currentUsage.append(station.usage)

			# generate feature vector for prediction model
			features.append(genFeature(nextDay, station.id, high, low, rain, snow))
			pred = models[index].predict(features[-1])
			if pred < 0:
				demands.append(0)
			else:
				demands.append(int(pred[0]))
		# get rid of prediction in the past and add a new one in the rolling prediction
		demandsNext.popleft()
		demandsNext.append(demands)

		print('\nDemand prediction for next 7 days:')
		print('------------------------------------')
		print(demandsNext)

		# cumulated demand for the rest of the week
		if nextDay == 1:
			cumulatedDemand = list(np.array(demandsNext).sum(axis=0))
			print("Cumulated:", cumulatedDemand)
		
			print("\nMaintenance prediction for each station next week:")
			print("------------------------------------")
			# which station may need service next week 
			maxUsage = s1.maxUsage # masusage are the same for all stations
			mayNeedService = []
			for station, demand in zip(stations, cumulatedDemand):
				bound = station.usage + demand
				if bound > maxUsage:
					mayNeedService.append("Might break down!!")
				elif bound > maxUsage / 2:
					mayNeedService.append("May request service.")
				else:
					mayNeedService.append("Good for now.")
			print(mayNeedService)
			# how many? 
			numNeedService = sum([1 if x != "Good for now." else 0 for x in mayNeedService ])
			print("Number of stations that might need service:", numNeedService)

			# select levels based on objective: max availability, max profit, ...
			Station._requestLevels = selectLevels(numNeedService, avail = 0, profit = 0, cost = 1)

		print('\nActual visits of each station today: ')
		print('------------------------------------')
		print(actualVisits)
		
		# check service request status	
		print("\nStation Maintenance Info:")
		print("------------------------------------")	
		for station in stations:
			if station.waiting:
				# try again if provider's inventory was full yesterday
				station.requestService(False)
			elif station.inService == 0:
				if station.pendingDays > 1: # being serviced, check days left
					print("Station", Station.stationDict[station.id], "being serviced:", station.pendingDays, "days left.")
					station.pendingDays -= 1
				elif station.pendingDays == 1: # back to operation
					station.pendingDays = 0
					station.usage = 0
					station.inService = 1
					Provider._inventory += 1
					print("Station", Station.stationDict[station.id], "being serviced: 1 day left, back in operation tomorrow.")
				else:
					pass
			elif station.usage > station.maxUsage: # over used, suspend
				station.inService = 0
				station.requestService(False)
			elif station.usage > station.maxUsage / 2: # start requesting maintenance when usage greater than half of max
				# request service when usage is above half of max
				station.requestService(False)

		input("\nPress Enter to continue...\n")

def getDayOfWeek(tomorrow):
	"""Get next day of week"""
	days = {1:'Monday',
	        2:'Tueday',
	        3:'Wednesday',
	        4:'Thursday',
	        5:'Friday',
	        6:'Saturday',
	        7:'Sunday'}

	return days[tomorrow]

def genWeather():
	"""generate weather data for one winter day"""
	maxTemp = random.uniform(20,30)
	minTemp = maxTemp - random.uniform(5,10)
	rain = 0
	snow = random.uniform(0,2)

	return [maxTemp, minTemp, rain, snow]

def genFeature(tomorrow, stationID, high, low, rain, snow):
	"""Generate 1 sample feature vector for demand prediction."""
	featureVec = pd.Series({'Monday':0,
		'Tueday':0,
		'Wednesday':0,
		'Thursday':0,
	    'Friday':0,
	    'Saturday':0,
	    'Sunday':0,
	    'holiday':0,
	    'winter':0,
	    'stationID':0,
	    'max':0,
	    'min':0,
	    'rain':0,
	    'snow':0})

	featureVec[tomorrow] = 1
	featureVec['stationID'] = stationID
	featureVec['winter'] = 1 # assume it's winter now - model only has winter as season because original test set uses 2016 data (Jan & Feb) 
	featureVec['max'] = high
	featureVec['min'] = low
	featureVec['rain'] = rain
	featureVec['snow'] = snow

	# reshape because 1D array only contains one sample
	return featureVec.reshape(1,-1)

def selectLevels(numNeedService, avail = 0, profit = 0, cost = 0):
	"""Select best request levels given the objective."""
	if avail + profit + cost == 0: # if objective is not given by user, maximize availability
		print("Maximization Objective not selected, default to maximizing availability.")
		avail = 1
	if avail == 1:
		# objective is to minimize sum of pendingDays
		# hard coded solution...
		# this solution maximizes the chance that all stations who request would get serviced,
		# while minimizing servicing time
		if numNeedService == 5:
			return [2,2,2,2,2]
		elif numNeedService == 4:
			return [2,2,3,3]
		elif numNeedService == 3:
			return [3,3,3]
		elif numNeedService == 2:
			return [3,3]
		elif numNeedService == 1:
			return [3]

	elif profit == 1:
		# objective is to maximize weekly profit
		# don't have to guarantee every station is serviced anymore, but serves as a tight upper bound
		if numNeedService == 5:
			return [2,2,3,3] # [1,1,1,3,3] might also work
		elif numNeedService == 4:
			return [2,2,3,3]
		elif numNeedService == 3:
			return [3,3,3]
		elif numNeedService == 2:
			return [3,3]
		elif numNeedService == 1:
			return [3]

	elif cost == 1:	
		# objective is to minimize weekly spending on station maintenance
		return [1,1,1,1,1]

if __name__ == '__main__':
	main()
