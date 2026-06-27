import csv

class FuelCell:

    type = "FUEL"

    def __init__(self, positionXY, fuel_temp = 25.0, mod_temp = 25.0, fission_matrix=None):
        self.positionXY = positionXY
        self.fuel_temp = fuel_temp
        self.mod_temp = mod_temp
        self.fission_rate = 100.0
        self.fission_matrix = fission_matrix
        self.temperature_matrix = temperature_matrix

    def getType(self):
        return self.type
    
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

    def setTemperatureMatrix(self, temperature_matrix):
        self.temperature_matrix = temperature_matrix

    def getTemperatureMatrix(self):
        return temperature_matrix

class ControlRod:

    type = "CONTROL_ROD"

    def __init__(self, positionXY, insertion=1.0):
        self.positionXY = positionXY
        self.insertion = insertion  # 1.0 - fully inserted, 0.0 - fully withdrawn

    def getType(self):
        return self.type
    
    def getPosition(self):
        return self.positionXY
    
    def setInsertion(self, insertion):
        self.insertion = insertion
    
    def getInsertion(self):
        return self.insertion

class EmptyChannel:

    type = "EMPTY_CHANNEL"

    def getType(self):
        return self.type

class Reactor:

    # Simulation constants
    beta = 0.0065            # Delayed neutron fraction
    _lambda = 3.0e-5         # Neutron lifetime, seconds
    t_fuel_baseline = 900.0  # Baseline fuel temperature, kelvin
    t_mod_baseline = 600.0   # Baseline moderator temperature, kelvin
    rho_baseline = 0.0       # Baseline reactivity
    beta_i = (0.00021, 0.00141, 0.00127, 0.00255, 0.00074, 0.00027)
    lambda_i = (0.0124, 0.0305, 0.1110, 0.3010, 1.1400, 3.0100)

    def __init__(self, dt=0.05):
        self.fuel_rods = []
        self.control_rods = []
        self.dt = dt  # Timestep, seconds

        self.fission_relations = []
        with open("fission_coupling_table_2.csv", mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                new_row = []
                for i in row:
                    new_row.append(float(i))
                fission_relations.append(new_row)

    def setTimestep(self, dt):
        self.dt = dt
    
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
