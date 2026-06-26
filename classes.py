import pandas as pd

class FuelCell:

    type = "FUEL"

    def __init__(self, positionXY, temperature = 25.0, fission_matrix=None):
        self.positionXY = positionXY
        self.temperature = temperature
        self.fission_rate = 0.0
        self.fission_matrix = fission_matrix
    
    def getPositionXY(self):
        return self.positionXY
    
    def setTemperature(self, temperature):
        self.temperature = temperature
    
    def getTemperature(self):
        return self.temperature
    
    def setFissionRate(self, fission_rate):
        self.fission_rate =- fission_rate
    
    def getFissionRate(self):
        return self.fission_rate
    
    def setFissionMatrix(self, fission_matrix):
        self.fission_matrix = fission_matrix
    
    def getFissionMatrix(self):
        return self.fission_matrix

class ControlRod:

    type = "CONTROL_ROD"

    def __init__(self, positionXY, insertion=1.0):
        self.positionXY = positionXY
        self.insertion = insertion
    
    def getPosition(self):
        return self.positionXY
    
    def setInsertion(self, insertion):
        self.insertion = insertion
    
    def getInsertion(self):
        return self.insertion

class Reactor:

    def __init__(self):
        self.fuel_rods = []
        self.control_rods = []
    
    def setFuelRods(self, fuel_rods):
        self.fuel_rods = fuel_rods
    
    def getFuelRods(self):
        return self.fuel_rods
    
    def getFuelRodsFissions(self):
        fuel_rods_fissions = []
        for i in self.fuel_rods:
            fuel_rods_fissions.append(i.getFissionRate())
        return fuel_rods_fissions
    
    def getFuelRodsTemperatures(self):
        fuel_rods_temperatures = []
        for i in self.fuel_rods:
            fuel_rods_temperatures.append(i.getTemperature())
        return fuel_rods_temperatures

    def applyFissionMatrices(self):
        for fuel_rod in self.fuel_rods:
            fission_matrix = fuel_rod.getFissionMatrix()
            for response_rod, dF in fission_matrix:
                response_rod.multiplyFission(in)