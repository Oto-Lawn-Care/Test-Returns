import csv
import timeit
import tkinter as tk
import tkinter.messagebox as msgBox
import tkinter.font as font
from typing import List
import pathlib
import datetime
from otoTests import * 
import ctypes
import datetime
import seaborn as sns  # for graphs
import matplotlib
import globalvars  # anyvariable/funtion you want globally available goes here
import serial
import pyoto.otoProtocol.otoCommands as pyoto
matplotlib.use('Agg')  # needed to prevent multi-thread failures when using matplotlib
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class VacError(Exception):
    pass

class EOLLocationError(Exception):
    pass

class LogFileLocationError(Exception):
    pass

class MainWindow(tk.Tk): 
    BAD_COLOUR = "RED"
    GOOD_COLOUR = "GREEN"
    IN_PROCESS_COLOUR = "YELLOW"
    NORMAL_COLOUR = "WHITE"
    SCALEFACTOR = 1  # scale factor is one if there are 1440 vertical pixels on the screen
    FIGSIZEX = 10.1  # width of chart window for a 1440 vertical pixel screen, to be scaled at the init stage
    FIGSIZEY = 6.5 # height of chart window, for a 1440 vertical pixel screen, to be scaled at the init stage
    DPI = 120  # scale based on monitor dots per inch
    
    def __init__(self):
        tk.Tk.__init__(self)
        self.tk.call("tk", "scaling", 1.33)  # needed to prevent graphs from growing during data updates
        self.SCALEFACTOR = self.winfo_screenheight() / 1440  # scaling based on screen size - sized for 2160 x 1440 screen
        self.FIGSIZEX = self.FIGSIZEX * self.SCALEFACTOR  # scaled width of chart window
        self.FIGSIZEY = self.FIGSIZEY * self.SCALEFACTOR  # scaled height of chart window
        sns.set_theme(font = "Microsoft YaHei", font_scale = self.SCALEFACTOR)  # sets the default seaborn chart colours and fonts

        self.device_list = TestPeripherals()
        self.test_suite = TestSuite(name="OtO END OF LINE PROGRAM  OtO检测程序 v4.5.4",
                            test_list=[
                                SetUnitName(name = "Unit Name  设备名称", parent = self),
                                TestBattery(name = "Battery  检查电池", parent = self),
                                TestExternalPower(name = "OtO Charging  OtO充电", parent = self),
                                TestPump(name = "Pump 1    1号泵", target_pump = 1, target_pump_duty = 100, parent = self),
                                TestPump(name = "Pump 2    2号泵", target_pump = 2, target_pump_duty = 100, parent = self),
                                TestPump(name = "Pump 3    3号泵", target_pump = 3, target_pump_duty = 100, parent = self),
                                GetAndSaveNozzleHomePosition(name = "Nozzle Position 设置喷嘴位置", parent = self),
                                EstablishZeroPressure(name = "Zero Pressure  检查零压力", data_collection_time = 2.1, class_function= "EOL" , valve_target = None, parent = self),
                                ValveCalibration(name = "Valve Calibration  校准阀门", parent = self, reset = True),
                                VerifyValveOffsetTarget(name = "Valve Closes? 验证阀门关闭", parent = self),
                                TestMoesFullyOpen(name = "Fully Open Test 阀门全打开测试", parent = self),
                                NozzleRotationTestWithSubscribe(name = "Nozzle Rotate  喷嘴旋转测试", parent = self),
                                CheckVacSwitch(name = "Pump Vacuum  检查泵真空", parent = self),
                                TestSolar(name = "Solar Panel  测试太阳能板", parent = self),
                                CloudSaveUnitAttributes(name = "Log Information  存储信息", parent = self),
                                PrintDeviceLabel(name = "Print Label  打印标签" , number_of_prints = 1, parent = self)
                                ],  
                            test_devices = self.device_list,
                            test_type = "EOL")
        
        self.csv_file_name:pathlib.Path = None
        self.log_file_directory: pathlib.Path = None

        # Fixed Window Elements
        self.status_font = font.Font(family = "Microsoft YaHei UI", size = int(19 * self.SCALEFACTOR), weight = "normal")
        self.smaller_font = font.Font(family = "Microsoft YaHei UI", size = int(17 * self.SCALEFACTOR), weight = "normal")
        self.winfo_toplevel().title(self.test_suite.name)
        self.text_console = tk.Text(self, relief = "raised", border = 3, font = font.Font(family = "Microsoft YaHei UI", size = int(17 * self.SCALEFACTOR), weight = "normal"), padx = int(10 * self.SCALEFACTOR), pady = int(10 * self.SCALEFACTOR), height = 6)
        self.GraphHolder = tk.Frame(self, bg = self.NORMAL_COLOUR, relief = "sunken", border = 3, width = int(1200 * self.SCALEFACTOR))
        self.GraphHolder.grid_propagate(False)
        self.label_batch_number = tk.Label(self, text = "Batch 批号:", font = self.status_font, padx = int(5 * self.SCALEFACTOR))
        self.label_device_id = tk.Label(self, text = "Unit Name:\n设备名称", font = self.smaller_font, padx = int(5 * self.SCALEFACTOR))
        self.text_device_id = tk.Text(self, width = 10, font = self.status_font, height = 1, padx = int(5 * self.SCALEFACTOR), pady = int(5 * self.SCALEFACTOR))
        self.label_bom_number = tk.Label(self, text = "BOM:", font = self.smaller_font, padx = int(5 * self.SCALEFACTOR))
        self.text_bom_number = tk.Text(self, width = 10, font = self.status_font, height = 1, padx = int(5 * self.SCALEFACTOR), pady = int(5 * self.SCALEFACTOR))
        self.label_new_flash = tk.Label(self, text = "NEW:\n新BOM:", font = self.smaller_font, padx = int(5 * self.SCALEFACTOR))
        if globalvars.BOMtoFlash == globalvars.KenakoreBOM:
            self.label2_new_flash = tk.Label(self, text = "RMA only", font = self.status_font, padx = 10)
        else:
            self.label2_new_flash = tk.Label(self, text = globalvars.BOMtoFlash, font = self.status_font, padx = 10)
        self.labelFirmware = tk.Label(self, text = "", font = self.smaller_font, padx = int(5 * self.SCALEFACTOR))
        self.labelFirmware2 = tk.Label(self, text = "Firmware\n固件", font = self.smaller_font, padx = int(5 * self.SCALEFACTOR))

        # Program Variables
        self.abort_test_bool: bool = False
        self.test_result_list: List[TestResult] = []
        self.test_start_time: float = 0.0

        # User-Created Window Elements
        self.status_labels: List[tk.Label] = []
        self.buttons: List[tk.Button] = []
        self.all_elements = [self.status_labels, self.buttons]

        # Widgets: Buttons
        self.one_button_to_rule_them_all = tk.Button(self, text = "Start    启动测试", width = 18, font = font.Font(family = "Microsoft YaHei UI", size = int(22 * self.SCALEFACTOR), weight = "bold"), pady = int(3 * self.SCALEFACTOR), bg = self.GOOD_COLOUR, fg = self.NORMAL_COLOUR, command = self.execute_tests)
        self.turn_valve_button = tk.Button(self, text = "Turn Valve  转动阀门", width = 18, font = font.Font(family = "Microsoft YaHei UI", size = int(22 * self.SCALEFACTOR), weight = "bold"), pady = int(3 * self.SCALEFACTOR), bg = self.GOOD_COLOUR, fg = self.NORMAL_COLOUR, command = self.TurnValve90)
        self.buttons.append(self.one_button_to_rule_them_all)
        self.buttons.append(self.turn_valve_button)

        # Grids for placement of elements
        self.label_batch_number.grid(row = 0, column = 0, columnspan = 2, sticky = "EW")
        self.text_console.grid(row = 0, column = 4, rowspan = 6, padx = int(5 * self.SCALEFACTOR), pady = int(5 * self.SCALEFACTOR), sticky = "NEWS")
        self.GraphHolder.grid(row = 6, column = 4, rowspan = 10, padx = int(5 * self.SCALEFACTOR), pady = 1, sticky = "NEWS")
        self.label_device_id.grid(row = 1, column = 0, sticky = "E", padx = int(10 * self.SCALEFACTOR))
        self.text_device_id.grid(row = 1, column = 1, sticky = "W", padx = int(5 * self.SCALEFACTOR), pady = int(5 * self.SCALEFACTOR))
        self.label_bom_number.grid(row = 2, column = 0, sticky = "E", padx = int(10 * self.SCALEFACTOR))
        self.text_bom_number.grid(row = 2, column = 1, sticky = "W", padx = int(5 * self.SCALEFACTOR), pady = int(5 * self.SCALEFACTOR))
        self.label_new_flash.grid(row = 3, column = 0, sticky = "E", padx = int(10 * self.SCALEFACTOR))
        self.label2_new_flash.grid(row = 3, column = 1, sticky = "W", padx = int(5 * self.SCALEFACTOR))
        self.labelFirmware2.grid(row = 4, column = 0, sticky = "E", padx = int(10 * self.SCALEFACTOR))
        self.labelFirmware.grid(row = 4, column = 1, sticky = "W", padx = int(5 * self.SCALEFACTOR))
        self.one_button_to_rule_them_all.grid(row = 6, column = 1, padx = int(5 * self.SCALEFACTOR), pady = int(5 * self.SCALEFACTOR))
        self.turn_valve_button.grid(row = 9, column = 1, padx = int(5 * self.SCALEFACTOR), pady = int(5 * self.SCALEFACTOR))

        # Normal Setup
        self.create_labels()

    def abort_test(self):
        "Function to STOP test"
        self.one_button_to_rule_them_all["state"] = "disabled"
        self.abort_test_bool = True
        self.one_button_to_rule_them_all.update()

    def clear_plot(self):
        "clears all items in the plot frame"
        for widgets in self.GraphHolder.winfo_children():
            widgets.destroy()

    def create_labels(self):
        '''
        this will take the test suite that it's given and create a tk.label for each.
        it will initialize the position as well.
        it stores the list of these labels so we can access and modify labels
        '''
        ColumnCount = 16  # number of items per column
        for count, steps in enumerate(self.test_suite.test_list):
            column_no = 3 + count // ColumnCount
            row_no = count % ColumnCount
            setattr(self, steps.name, tk.Button(self, borderwidth = 3, relief = "sunken", text = steps.name, bg = self.NORMAL_COLOUR, font = self.status_font, padx = int(10 * self.SCALEFACTOR), pady = int(10 * self.SCALEFACTOR), width = 25, command = lambda x=count : self.OneTestButton(x)))
            temp = getattr(self, steps.name)
            self.status_labels.append(temp)
            temp.grid(row = row_no, column = column_no, sticky = "EW", padx = int(3 * self.SCALEFACTOR), pady = int(3 * self.SCALEFACTOR))

    def create_plot(self, window, plottype: str, xaxis, yaxis, size, name, clear):
        """creates a plot of type histogram, line, or polar in the plot frame"""
        self.clear_plot()
        plotit = False
        if plottype == "histplot":
            figure = plt.figure(0, figsize = (self.FIGSIZEX, self.FIGSIZEY), dpi = self.DPI)
            sns.histplot(data = xaxis)
            plt.title(name)
            plotit = True
        elif plottype == "fohistplot":
            figure = plt.figure(2, figsize = (self.FIGSIZEX, self.FIGSIZEY), dpi = self.DPI)
            sns.histplot(data = xaxis)
            plt.title(name)
            plotit = True
        elif plottype == "lineplot":
            figure = plt.figure(1, figsize = (self.FIGSIZEX, self.FIGSIZEY), dpi = self.DPI)
            if size > 10:
                sns.scatterplot(x = xaxis, y = yaxis, marker = "o", s = size)
            else:
                sns.lineplot(x = xaxis, y = yaxis)
            plt.title(name)
            plotit = True
        elif plottype == "polar":
            figure = plt.figure(3, figsize = (self.FIGSIZEX, self.FIGSIZEY), dpi = self.DPI)
            plt.polar(xaxis, yaxis, "r")
            plt.title(name)
            plotit = True
        if plotit:
            canvas = FigureCanvasTkAgg(figure, master = window)
            canvas.get_tk_widget().grid()
            self.GraphHolder.update()
            if clear:
                plt.close()

    def eol_pcb_init(self):
        """turns all EOL board pins off"""
        self.test_suite.test_devices.gpioSuite.ledPanelPin.set(1)
        self.test_suite.test_devices.gpioSuite.airSolenoidPin.set(1)
        self.test_suite.test_devices.gpioSuite.extPowerPin.set(1)
        self.test_suite.test_devices.gpioSuite.waterSolenoidPin.set(1)

    def establish_file_write_location(self):
        "sets and creates the directory for writing the main weekly data file for this station"
        is_testing = False  # set this to True to store data outside of the production folder
        if self.test_suite.test_devices.DUTsprinkler.logFileDirectory is None:
            self.test_suite.test_devices.DUTsprinkler.logFileDirectory = pathlib.Path("C:\Data")
            pathlib.Path(self.test_suite.test_devices.DUTsprinkler.logFileDirectory).mkdir(parents = True, exist_ok = True)
        self.log_file_directory = self.test_suite.test_devices.DUTsprinkler.logFileDirectory
        if is_testing == True:
            test_folder = "Test Folder"
            self.log_file_directory = (pathlib.Path(self.log_file_directory) /  test_folder)
            filename = "-TestProductionData" + str(time.strftime("%y", time.localtime())) + format(datetime.datetime.now().isocalendar()[1],"02d") + ".csv"
        else: 
            filename = "ProductionData" + str(time.strftime("%y", time.localtime())) + format(datetime.datetime.now().isocalendar()[1],"02d") + ".csv"
        self.csv_file_name = (pathlib.Path(self.log_file_directory)/(str(self.test_suite.test_devices.DUTsprinkler.testFixtureName) + filename ))

    def execute_tests(self):
        "called when START button is pressed"
        if self.one_button_to_rule_them_all["state"] == "disabled" or self.turn_valve_button["state"] == "disabled":
            return None  # running another test, so don't start a new one
        else:
            self.turn_valve_button.configure(state = "disabled") # prevent button from working
            self.one_button_to_rule_them_all.configure(text = "STOP  停止测试", bg = self.IN_PROCESS_COLOUR, fg = "BLACK", command = self.abort_test, state = "normal") 
            self.one_button_to_rule_them_all.update()

        # Step 1: Reinitialize Program Variables
        self.abort_test_bool: bool = False
        self.test_result_list: List[TestResult] = []
        self.test_start_time: float = 0.0

        # Step 2: Clean up window view, check for more than 1 USB board attached, start timer
        self.reset_status_color()
        if not self.USBCheck():
            self.text_console.configure(bg = self.IN_PROCESS_COLOUR)
            self.text_console_logger("Too many USB cards attached for EOL test\n太多测试板连接到终端测试上")
            self.one_button_to_rule_them_all.configure(text = "Start    启动测试", bg = self.GOOD_COLOUR, fg = self.NORMAL_COLOUR, command = self.execute_tests, state = "normal")
            self.turn_valve_button.configure(state = "normal")
            return None
        self.test_start_time = timeit.default_timer()

        try:  # All encompassing error catch

            # Step 3: Restart device and reinitialize objects
            self.initialize_devices()
            if self.test_suite.test_type == "EOL": # reset all pin states
                self.eol_pcb_init()
                self.vac_interrupt()

            #Step 4: Run the test Suite
            index = 0
            self.label_batch_number.configure(text = "Batch 批号: " + self.test_suite.test_devices.DUTsprinkler.batchNumber)
            while self.abort_test_bool is False and index < len(self.test_suite.test_list):
                self.status_labels[index].config(bg = self.IN_PROCESS_COLOUR)
                self.status_labels[index].update()
                self.test_result_list.append(self.test_suite.test_list[index].run_step(peripherals_list=self.test_suite.test_devices))
                if not self.test_result_list[index].is_passed:
                    self.test_step_failure_handler(step_number = index)
                    self.test_suite.test_devices.DUTsprinkler.passTime = round((timeit.default_timer() - self.test_start_time), 4)
                    self.log_unit_data()
                    self.one_button_to_rule_them_all.configure(text = "Start    启动测试", bg = self.GOOD_COLOUR, fg = self.NORMAL_COLOUR, command = self.execute_tests, state = "normal")
                    self.turn_valve_button.configure(state = "normal")
                    return ClosePort(self.device_list)
                else:
                    self.status_labels[index].configure(bg = self.GOOD_COLOUR)
                    self.status_labels[index].update()
                    if self.test_result_list[index].test_status != None:
                        self.text_console_logger(display_message = self.test_result_list[index].test_status[1:])
                    index += 1

            #Step 5: While Loop Complete or Escaped
            if self.abort_test_bool is True:
                self.text_console_logger(display_message="Stop button pressed, no results saved.  按下停止按钮, 未保存结果.")
                self.text_console_logger('-----------------------Test was STOPPED   测试已停止----------------------------')
                self.one_button_to_rule_them_all.configure(text = "Start    启动测试", bg = self.GOOD_COLOUR, fg = self.NORMAL_COLOUR, command = self.execute_tests, state = "normal")
                self.turn_valve_button.configure(state = "normal")
                return ClosePort(self.device_list)
            else:
                self.test_suite.test_devices.DUTsprinkler.passEOL = True
                self.test_suite.test_devices.DUTsprinkler.passTime = round((timeit.default_timer() - self.test_start_time), 4)
                self.log_unit_data()
                self.text_console_logger("--------------------------Device PASSED  测试通过-------------------------------")

            # Step 6: Reset Button Status
            self.one_button_to_rule_them_all.configure(text = "Start    启动测试", bg = self.GOOD_COLOUR, fg = self.NORMAL_COLOUR, command = self.execute_tests, state = "normal")
            self.turn_valve_button.configure(state = "normal")

        except Exception as e:
            if hasattr(self.test_suite.test_devices, "gpioSuite"):
                self.eol_pcb_init()  # Turns off power, air and LED
            self.text_console.configure(bg = self.IN_PROCESS_COLOUR)
            if str(e) == "Ping Failed":
                self.text_console_logger("No OtO found. Check that the grey ribbon cable is plugged into OtO.\n未发现洒水器。检查测试板上的灰色线是否接到洒水器上")
            elif str(e) == "No Otos found on Serial Ports":
                self.text_console_logger("No serial card found. Check that the USB communication serial card is plugged in.\n未发现测试板。检查USB通信测试板是否连接上USB接口")
            else:
                if len(str(e)) > 0:
                    self.text_console_logger(display_message = str(e))
                else:
                    self.text_console_logger(display_message = "UNEXPECTED PROGRAM ERROR!  未知程序错误")
            self.one_button_to_rule_them_all.configure(text = "Start    启动测试", bg = self.GOOD_COLOUR, fg = self.NORMAL_COLOUR, command = self.execute_tests, state = "normal")
            self.turn_valve_button.configure(state = "normal")

        return ClosePort(self.device_list)

    def initialize_devices(self):
        '''
        Add an otoSprinkler instance, establish the gpio and i2c communications to the Cypress chip.
        Figure out where the EOL PCB is located (MECO or OTO?) and its identity (which fixture number to help determine what testStep limits to use)
        '''
        try:
            if self.test_suite.test_type == "EOL":
                if not hasattr(self.test_suite.test_devices, "gpioSuite"):
                    new_gpio = GpioSuite()
                    self.test_suite.test_devices.add_device(new_object = new_gpio)
                if not hasattr(self.test_suite.test_devices,"i2cSuite"):
                    new_i2c = I2CSuite()
                    self.test_suite.test_devices.add_device(new_object = new_i2c)
                self.text_console_logger("Connecting to OtO 正在连接洒水器...")
                new_oto = otoSprinkler()
                self.test_suite.test_devices.add_device(new_object = new_oto)  # always reinitialize connection and create new sprinkler
                self.labelFirmware.configure(text = self.test_suite.test_devices.DUTsprinkler.Firmware)
                self.labelFirmware.update()
                # pull info from the EOL PCB. factoryLocation and 
                self.test_suite.test_devices.DUTsprinkler.factoryLocation, self.test_suite.test_devices.DUTsprinkler.testFixtureName = self.test_suite.test_devices.gpioSuite.getBoardInfo()
            else:
                self.text_console_logger(display_message = "UNEXPECTED PROGRAM ERROR!  未知程序错误")
        except Exception as e:
            raise Exception(e)

    def log_unit_data(self):
        '''
        logging raw data about the testSteps. required to help us determine limits for each testStep per fixture.
        Every single testStep in the testSuite run must be added to this function otherwise it will error out
        '''
        write_header: bool = True
        self.establish_file_write_location()
        log_file_columns = ["Entry Time", "Device ID", "MAC Address", "Firmware", "BOM", "Batch", "Unit Name Time", "Battery", "Battery Time", "Ext Power I","Ext Power V", "Ext Power Time",
                            "Pump 1 Time", "Pump 1 Ave Current", "Pump 1 Current STD", "Pump 2 Time", "Pump 2 Ave Current", "Pump 2 Current STD", "Pump 3 Time", "Pump 3 Ave Current", "Pump 3 Current STD",
                            "Nozzle Offset", "Nozzle Home Time","0 Pressure", "0 Pressure STD", "0 Pressure Time", "Valve Offset", "Valve Offset Time", "Valve Ave Current", "Valve Current STD",
                            "Peak 1 Pressure", "Peak 1 Angle", "Peak 2 Pressure", "Peak 2 Angle", "Closed Pressure", "Closed Pressure STD", "Closed Pressure Time", "Fully Open Trials",
                            "Fully Open 1 Ave", "Fully Open 1 STD", "Fully Open 3 Ave", "Fully Open 3 STD", "Fully Open Time", "Nozzle Speed", "Nozzle Speed STD", "Nozzle Time", "Nozzle Ave Current",
                            "Nozzle Current STD", "Vacuum Fail", "Vacuum Time", "Solar Voltage", "Solar Current", "Solar Time", "Cloud Save", "Cloud Time", "Printed", "Print Time", "Pass Time", "Passed"]

        if pathlib.Path(self.csv_file_name).exists():
            write_header = False
        else:
            pathlib.Path(self.log_file_directory).mkdir(parents = True, exist_ok = True)

        with open(self.csv_file_name, mode = "a", newline = "") as log_file:
            csv_writer = csv.DictWriter(log_file, fieldnames = log_file_columns)
            if write_header is True:
                csv_writer.writeheader()
            default_row = { "Entry Time": datetime.datetime.now(),
                            "Device ID": self.test_suite.test_devices.DUTsprinkler.deviceID,
                            "MAC Address": self.test_suite.test_devices.DUTsprinkler.macAddress,
                            "Firmware": self.test_suite.test_devices.DUTsprinkler.Firmware,
                            "BOM": self.test_suite.test_devices.DUTsprinkler.bomNumber,
                            "Batch": self.test_suite.test_devices.DUTsprinkler.batchNumber,
                            "Unit Name Time": None,
                            "Battery": None,
                            "Battery Time": None,
                            "Ext Power I": None,
                            "Ext Power V": None,
                            "Ext Power Time": None,
                            "Pump 1 Time": None,
                            "Pump 1 Ave Current": None,
                            "Pump 1 Current STD": None,
                            "Pump 2 Time": None,
                            "Pump 2 Ave Current": None,
                            "Pump 2 Current STD": None,
                            "Pump 3 Time": None,
                            "Pump 3 Ave Current": None,
                            "Pump 3 Current STD": None,
                            "Nozzle Offset": None,
                            "Nozzle Home Time": None,
                            "0 Pressure": None,
                            "0 Pressure STD": None,
                            "0 Pressure Time": None,
                            "Valve Offset": None,
                            "Valve Offset Time": None,
                            "Valve Ave Current": None,
                            "Valve Current STD": None,
                            "Peak 1 Pressure": None,
                            "Peak 1 Angle": None,
                            "Peak 2 Pressure": None,
                            "Peak 2 Angle": None,
                            "Closed Pressure": None,
                            "Closed Pressure STD": None,
                            "Closed Pressure Time": None,                            
                            "Fully Open Trials": None,
                            "Fully Open 1 Ave": None,
                            "Fully Open 1 STD": None,
                            "Fully Open 3 Ave": None,
                            "Fully Open 3 STD": None,
                            "Fully Open Time": None,
                            "Nozzle Speed": None,
                            "Nozzle Speed STD": None,
                            "Nozzle Time": None,
                            "Nozzle Ave Current": None,
                            "Nozzle Current STD": None,
                            "Vacuum Fail": None,
                            "Vacuum Time": None,
                            "Solar Voltage": None,
                            "Solar Current": None,
                            "Solar Time": None,
                            "Cloud Save": None,
                            "Cloud Time": None,
                            "Printed": None,
                            "Print Time": None,
                            "Pass Time": self.test_suite.test_devices.DUTsprinkler.passTime,
                            "Passed": self.test_suite.test_devices.DUTsprinkler.passEOL
                            }

            CurrentPump = 1
            for entry in self.test_result_list:
                if entry.cycle_time > 0:
                    if isinstance(entry, SetUnitNameResult):
                        default_row["Unit Name Time"] = entry.cycle_time
                    elif isinstance(entry, TestBatteryResult):
                        default_row["Battery Time"] = entry.cycle_time
                        default_row["Battery"] = self.test_suite.test_devices.DUTsprinkler.batteryVoltage
                    elif isinstance(entry, TestExternalPowerResult):
                        default_row["Ext Power Time"] = entry.cycle_time
                        default_row["Ext Power I"] = self.test_suite.test_devices.DUTsprinkler.extPowerCurrent
                        default_row["Ext Power V"] = self.test_suite.test_devices.DUTsprinkler.extPowerVoltage
                    elif isinstance(entry, TestPumpResult):
                        if CurrentPump == 1:
                            default_row["Pump 1 Time"] = entry.cycle_time
                            default_row["Pump 1 Ave Current"] = self.test_suite.test_devices.DUTsprinkler.Pump1CurrentAve
                            default_row["Pump 1 Current STD"] = self.test_suite.test_devices.DUTsprinkler.Pump1CurrentSTD
                            CurrentPump += 1
                        elif CurrentPump == 2:
                            default_row["Pump 2 Time"] = entry.cycle_time
                            default_row["Pump 2 Ave Current"] = self.test_suite.test_devices.DUTsprinkler.Pump2CurrentAve
                            default_row["Pump 2 Current STD"] = self.test_suite.test_devices.DUTsprinkler.Pump2CurrentSTD
                            CurrentPump += 1
                        elif CurrentPump == 3:
                            default_row["Pump 3 Time"] = entry.cycle_time
                            default_row["Pump 3 Ave Current"] = self.test_suite.test_devices.DUTsprinkler.Pump3CurrentAve
                            default_row["Pump 3 Current STD"] = self.test_suite.test_devices.DUTsprinkler.Pump3CurrentSTD
                            CurrentPump += 1
                    elif isinstance(entry, GetNozzleHomePositionResult):
                        default_row["Nozzle Home Time"] = entry.cycle_time
                        default_row["Nozzle Offset"] = self.test_suite.test_devices.DUTsprinkler.nozzleOffset
                    elif isinstance(entry, EstablishZeroPressureResult):
                        default_row["0 Pressure Time"] = entry.cycle_time
                        default_row["0 Pressure"] = self.test_suite.test_devices.DUTsprinkler.ZeroPressureAve
                        default_row["0 Pressure STD"] = self.test_suite.test_devices.DUTsprinkler.ZeroPressureSTD
                    elif isinstance(entry, ValveCalibrationResult):
                        default_row["Valve Offset Time"] = entry.cycle_time
                        default_row["Valve Ave Current"] = self.test_suite.test_devices.DUTsprinkler.ValveCurrentAve
                        default_row["Valve Current STD"] = self.test_suite.test_devices.DUTsprinkler.ValveCurrentSTD
                        default_row["Valve Offset"] = self.test_suite.test_devices.DUTsprinkler.valveOffset
                        default_row["Peak 1 Pressure"] = self.test_suite.test_devices.DUTsprinkler.ValvePeak1
                        default_row["Peak 1 Angle"] = self.test_suite.test_devices.DUTsprinkler.Peak1Angle
                        default_row["Peak 2 Pressure"] = self.test_suite.test_devices.DUTsprinkler.ValvePeak2
                        default_row["Peak 2 Angle"] = self.test_suite.test_devices.DUTsprinkler.Peak2Angle
                    elif isinstance(entry, VerifyValveOffsetTargetResult):
                        default_row["Closed Pressure Time"] = entry.cycle_time
                        if self.test_suite.test_devices.DUTsprinkler.valveClosesAve > 0:
                            default_row["Closed Pressure"] = self.test_suite.test_devices.DUTsprinkler.valveClosesAve
                            default_row["Closed Pressure STD"] = self.test_suite.test_devices.DUTsprinkler.valveClosesSTD
                    elif isinstance(entry, TestMoesFullyOpenResult):
                        default_row["Fully Open Time"] = entry.cycle_time
                        if self.test_suite.test_devices.DUTsprinkler.valveFullyOpenTrials > 0:
                            default_row["Fully Open Trials"] = self.test_suite.test_devices.DUTsprinkler.valveFullyOpenTrials
                            default_row["Fully Open 1 Ave"] = self.test_suite.test_devices.DUTsprinkler.valveFullyOpen1Ave
                            default_row["Fully Open 1 STD"] = self.test_suite.test_devices.DUTsprinkler.valveFullyOpen1STD
                            default_row["Fully Open 3 Ave"] = self.test_suite.test_devices.DUTsprinkler.valveFullyOpen3Ave
                            default_row["Fully Open 3 STD"] = self.test_suite.test_devices.DUTsprinkler.valveFullyOpen3STD
                    elif isinstance(entry, NozzleRotationTestWithSubscribeResult):
                        default_row["Nozzle Time"] = entry.cycle_time
                        default_row["Nozzle Ave Current"] = self.test_suite.test_devices.DUTsprinkler.NozzleCurrentAve
                        default_row["Nozzle Current STD"] = self.test_suite.test_devices.DUTsprinkler.NozzleCurrentSTD
                        if self.test_suite.test_devices.DUTsprinkler.nozzleRotationAve > 0:
                            default_row["Nozzle Speed"] = self.test_suite.test_devices.DUTsprinkler.nozzleRotationAve
                            default_row["Nozzle Speed STD"] = self.test_suite.test_devices.DUTsprinkler.nozzleRotationSTD
                    elif isinstance(entry, CheckVacSwitchResult):
                        default_row["Vacuum Time"] = entry.cycle_time
                        default_row["Vacuum Fail"] = self.test_suite.test_devices.DUTsprinkler.vacuumFail
                    elif isinstance(entry, TestSolarResult):
                        default_row["Solar Time"] = entry.cycle_time
                        default_row["Solar Voltage"] = self.test_suite.test_devices.DUTsprinkler.solarVoltage
                        default_row["Solar Current"] = self.test_suite.test_devices.DUTsprinkler.solarCurrent                    
                    elif isinstance(entry, CloudSaveUnitAttributesResult):
                        default_row["Cloud Time"] = entry.cycle_time
                        default_row["Cloud Save"] = self.test_suite.test_devices.DUTsprinkler.CloudSave
                    elif isinstance(entry, PrintDeviceLabelResult):
                        default_row["Print Time"] = entry.cycle_time
                        default_row["Printed"] = self.test_suite.test_devices.DUTsprinkler.Printed
                    else:
                        print (type(entry))
                        raise TypeError(f'Program error, unknown test specified: {entry}')
            csv_writer.writerow(default_row)
    
    def OneTestButton(self, ButtonNumber):
        """function for handling single button press for device debugging purposes"""
        if self.one_button_to_rule_them_all["state"] == "disabled" or self.turn_valve_button["state"] == "disabled":
            return None  # running another test, so don't start a new one
        else:
            self.one_button_to_rule_them_all.configure(state = "disabled")
            self.turn_valve_button.configure(state = "disabled")
        self.reset_status_color()
        FunctionName = self.status_labels[ButtonNumber]['text']
        self.text_console_logger(f"{FunctionName}...")
        self.status_labels[ButtonNumber].configure(bg = self.IN_PROCESS_COLOUR, state = "disabled")
        self.status_labels[ButtonNumber].update()
        if not self.USBCheck():
            self.text_console.configure(bg = self.IN_PROCESS_COLOUR)
            self.text_console_logger("Too many USB cards attached for EOL test\n太多测试板连接到终端测试上")
            self.status_labels[ButtonNumber].configure(bg = self.NORMAL_COLOUR, state = "normal")
            self.status_labels[ButtonNumber].update()
            self.one_button_to_rule_them_all.configure(state = "normal")
            self.turn_valve_button.configure(state = "normal")
            return None

        if FunctionName in "Nozzle Position 设置喷嘴位置 Pump Vacuum  检查泵真空 Log Information  存储信息 Print Label  打印标签":
            self.text_console_logger("This test cannot be run by itself.  此测试不能单独执行")
            self.status_labels[ButtonNumber].configure(bg = self.NORMAL_COLOUR, state = "normal")
            self.status_labels[ButtonNumber].update()
            self.one_button_to_rule_them_all.configure(state = "normal")
            self.turn_valve_button.configure(state = "normal")
            return None
        elif FunctionName in "Battery  检查电池 Zero Pressure  检查零压力":  # these functions don't need control board
            try:
                self.text_console_logger("Connecting to OtO 正在连接洒水器...")
                self.test_suite.test_devices.add_device(new_object = otoSprinkler())
            except Exception as e:
                self.text_console.configure(bg = self.IN_PROCESS_COLOUR)
                if str(e) == "Ping Failed":
                    self.text_console_logger("No OtO found. Check that the grey ribbon cable is plugged into OtO.\n未发现洒水器。检查测试板上的灰色线是否接到洒水器上")
                elif str(e) == "No Otos found on Serial Ports":
                    self.text_console_logger("No serial card found. Check that the USB communication serial card is plugged in.\n未发现测试板。检查USB通信测试板是否连接上USB接口")
                else:
                    self.text_console_logger(display_message = str(e))
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal") 
                return ClosePort(self.device_list)
            ResultList = self.test_suite.test_list[ButtonNumber].run_step(peripherals_list=self.test_suite.test_devices)
            if not ResultList.is_passed:
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger(display_message = ResultList.test_status)
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
            else:
                self.status_labels[ButtonNumber].configure(bg = self.GOOD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")  
            return ClosePort(self.device_list)             
        try:  # all other functions require an OtO, so try to connect to one first...
            if FunctionName in "Pump 1    1号泵 Pump 2    2号泵 Pump 3    3号泵":
                self.vac_interrupt()
            self.initialize_devices()
            self.eol_pcb_init()
        except Exception as e:
            self.text_console.configure(bg = self.IN_PROCESS_COLOUR)
            if str(e) == "Ping Failed":
                self.text_console_logger("No OtO found. Check that the grey ribbon cable is plugged into OtO.\n未发现洒水器。检查测试板上的灰色线是否接到洒水器上")
            elif str(e) == "No Otos found on Serial Ports":
                self.text_console_logger("No serial card found. Check that the USB communication serial card is plugged in.\n未发现测试板。检查USB通信测试板是否连接上USB接口")
            else:
                if len(str(e)) > 0:
                    self.text_console_logger(display_message = str(e))
                else:
                    self.text_console_logger(display_message = "UNEXPECTED PROGRAM ERROR!  未知程序错误")
            self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
            self.one_button_to_rule_them_all.configure(state = "normal")
            self.turn_valve_button.configure(state = "normal")               
            return ClosePort(self.device_list)
        if FunctionName in "Pump 1    1号泵 Pump 2    2号泵 Pump 3    3号泵":
            ResultList = self.test_suite.test_list[ButtonNumber].run_step(peripherals_list=self.test_suite.test_devices)
            if not ResultList.is_passed:
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger(display_message = ResultList.test_status)
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
            else:
                self.status_labels[ButtonNumber].configure(bg = self.GOOD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
        elif FunctionName in "Unit Name  设备名称": 
            ResultList = self.test_suite.test_list[ButtonNumber].run_step(peripherals_list=self.test_suite.test_devices)
            if not ResultList.is_passed:
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger(display_message = ResultList.test_status)
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
            else:
                self.status_labels[ButtonNumber].configure(bg = self.GOOD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")  
            return ClosePort(self.device_list)                
        elif FunctionName in "OtO Charging  OtO充电":  # get BOM and battery voltage to determine limits
            ResultList = self.test_suite.test_list[1].run_step(peripherals_list=self.test_suite.test_devices)  # Battery Voltage
            if not ResultList.is_passed:
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger(display_message = ResultList.test_status)
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
            else:
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
                    ResultList = self.test_suite.test_list[ButtonNumber].run_step(peripherals_list=self.test_suite.test_devices)  # OtO Charging
                    if not ResultList.is_passed:
                        self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                        self.status_labels[ButtonNumber].update()
                        self.text_console.configure(bg = self.BAD_COLOUR)
                        self.text_console_logger(display_message = ResultList.test_status)
                        self.one_button_to_rule_them_all.configure(state = "normal")
                        self.turn_valve_button.configure(state = "normal")
                    else:
                        self.status_labels[ButtonNumber].configure(bg = self.GOOD_COLOUR, state = "normal")
                        self.status_labels[ButtonNumber].update()
                        if ResultList.test_status != None:
                            self.text_console_logger(display_message = ResultList.test_status[1:])
                        self.one_button_to_rule_them_all.configure(state = "normal")
                        self.turn_valve_button.configure(state = "normal")                           
        elif FunctionName in "Valve Calibration  校准阀门":
            ResultList = ValveCalibration(name = "Valve Calibration 校准阀门", parent = self, reset = False).run_step(peripherals_list = self.test_suite.test_devices)  # Run valve calibration
            if not ResultList.is_passed:
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger(display_message = ResultList.test_status)
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
            else:
                self.status_labels[ButtonNumber].configure(bg = self.GOOD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")                           
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
        elif FunctionName in "Valve Closes? 验证阀门关闭 Fully Open Test 阀门全打开测试 Nozzle Rotate  喷嘴旋转测试":  # must turn air on and off to run these commands
            ResultList = self.test_suite.test_list[ButtonNumber].run_step(peripherals_list=self.test_suite.test_devices)  # Run selected test
            if not ResultList.is_passed:
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger(display_message = ResultList.test_status)
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
            else:
                self.status_labels[ButtonNumber].configure(bg = self.GOOD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
        elif FunctionName in "Solar Panel  测试太阳能板":
            ResultList = self.test_suite.test_list[ButtonNumber].run_step(peripherals_list=self.test_suite.test_devices)  # Solar Panel Test
            if not ResultList.is_passed:
                self.status_labels[ButtonNumber].configure(bg = self.BAD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger(display_message = ResultList.test_status)
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")
            else:
                self.status_labels[ButtonNumber].configure(bg = self.GOOD_COLOUR, state = "normal")
                self.status_labels[ButtonNumber].update()
                if ResultList.test_status != None:
                    self.text_console_logger(display_message = ResultList.test_status[1:])
                self.one_button_to_rule_them_all.configure(state = "normal")
                self.turn_valve_button.configure(state = "normal")                           
        return ClosePort(self.device_list)
    
    def reset_status_color(self):
        "Resets all the status box colors to normal"
        for widgets in self.status_labels:
            widgets.configure(bg = self.NORMAL_COLOUR)
            widgets.update()
        self.text_console.configure(bg = self.NORMAL_COLOUR)
        self.text_console.update()
        self.text_device_id.delete(1.0, tk.END)
        self.text_bom_number.delete(1.0, tk.END)
        self.labelFirmware.configure(text = "")
        self.text_device_id.update()
        self.clear_plot()
        ClearFigures()

    def test_step_failure_handler(self, step_number: int):
        '''
        the index is required to help display the correct message and log the correct error
        Updates the label to red in the gui, runs the cloud function to log the error in Firebase,
        resets all the gpio pins to the OFF state
        '''
        error_message = self.test_result_list[step_number].test_status
        self.test_suite.test_devices.DUTsprinkler.errorStep = error_message
        self.test_suite.test_devices.DUTsprinkler.errorStepName = type(self.test_result_list[step_number]).__name__
        self.status_labels[step_number].configure(bg = self.BAD_COLOUR)
        self.status_labels[step_number].update()
        self.text_console.configure(bg = self.BAD_COLOUR)
        self.text_console_logger(display_message = error_message)
        self.text_console_logger(display_message = "Logging OtO unit error information  记录洒水器测试错误信息，请稍等...")
        cloudLogResult = CloudLogMfgError(name = "unit_failure", parent = self).run_step(peripherals_list = self.test_suite.test_devices)
        if cloudLogResult.is_passed is not True:
            self.text_console_logger(display_message = cloudLogResult.test_status)
        self.eol_pcb_init()  # Turns off power, air and LED
        self.text_console_logger('------------------------------  DEVICE FAILED   测试不合格  -------------------------------------')

    def text_console_logger(self, display_message: str):
        """function to put text into the consle of the gui"""
        self.text_console.insert(tk.END,display_message + "\n")
        self.text_console.see(tk.END)
        self.text_console.update()

    def TurnValve90(self):
        """Turns the valve 90 degrees. Open valve for the 15 psi air leak check"""
        if self.one_button_to_rule_them_all["state"] == "disabled" or self.turn_valve_button["state"] == "disabled":
            return None
        else:
            self.one_button_to_rule_them_all.configure(state = "disabled")
            self.turn_valve_button.configure(state = "disabled")

        self.reset_status_color()
        self.turn_valve_button.configure(text = "Turning...", bg = self.IN_PROCESS_COLOUR, state = "disabled")
        self.one_button_to_rule_them_all.configure(state = "disabled")
        self.text_console.configure(bg = self.NORMAL_COLOUR)
        self.text_console_logger("Turning ball valve 90°  球阀旋转90°...")

        if not self.USBCheck():
            self.text_console.configure(bg = self.IN_PROCESS_COLOUR)
            self.text_console_logger("Too many USB cards attached for EOL test\n太多测试板连接到终端测试上")
            self.one_button_to_rule_them_all.configure(state = "normal")
            self.turn_valve_button.configure(state = "normal")
            return None

        try:
            self.text_console_logger("Connecting to OtO 正在连接洒水器...")
            self.test_suite.test_devices.add_device(new_object = otoSprinkler())
        except Exception as e:
            self.text_console.configure(bg = self.IN_PROCESS_COLOUR)
            if str(e) == "Ping Failed":
                self.text_console_logger("No OtO found. Check that the grey ribbon cable is plugged into OtO.\n未发现洒水器。检查测试板上的灰色线是否接到洒水器上")
            elif str(e) == "No Otos found on Serial Ports":
                self.text_console_logger("No serial card found. Check that the USB communication serial card is plugged in.\n未发现测试板。检查USB通信测试板是否连接上USB接口")
            else:
                if len(str(e)) > 0:
                    self.text_console_logger(display_message = str(e))
                else:
                    self.text_console_logger(display_message = "UNEXPECTED PROGRAM ERROR!  未知程序错误")
            self.one_button_to_rule_them_all.configure(state = "normal")
            self.turn_valve_button.configure(text = "Turn Valve  转动阀门", bg = self.GOOD_COLOUR, command = self.TurnValve90, state = "normal") 
            return ClosePort(self.device_list)

        try:
            currentPosition = int(self.test_suite.test_devices.DUTMLB.get_sensors().valve_position_centideg)
            desiredPosition = (currentPosition + 9000) % 36000
            ReturnMessage = self.test_suite.test_devices.DUTMLB.set_valve_position(valve_position_centideg = desiredPosition, wait_for_complete = True)
            if ReturnMessage.message_type_string != "CTRL_OUT_COMMAND_COMPLETE":
                self.text_console.configure(bg = self.BAD_COLOUR)
                self.text_console_logger("Valve turn was NOT successful.")
                self.turn_valve_button.configure(text = "Turn Valve  转动阀门", bg = self.GOOD_COLOUR, command = self.TurnValve90, state = "normal")
                self.one_button_to_rule_them_all.configure(state = "normal")            
                return ClosePort(self.device_list)
        except Exception as e:
            self.text_console.configure(bg = self.BAD_COLOUR)
            if e == TimeoutError:
                self.text_console_logger("OtO timed out trying to turn the valve.  洒水器尝试旋转球阀超时")
                self.text_console_logger("Valve turn was NOT successful.  旋转球阀失败")
            else:
                if len(str(e)) > 0:
                    self.text_console_logger(display_message = str(e))
                else:
                    self.text_console_logger(display_message = "UNEXPECTED PROGRAM ERROR!  未知程序错误")
            self.turn_valve_button.configure(text = "Turn Valve  转动阀门", bg = self.GOOD_COLOUR, command = self.TurnValve90, state = "normal")
            self.one_button_to_rule_them_all.configure(state = "normal")            
            return ClosePort(self.device_list)
        self.text_console_logger(display_message = "Valve successfully turned.  球阀旋转成功")
        self.turn_valve_button.configure(text = "Turn Valve  转动阀门", bg = self.GOOD_COLOUR, command = self.TurnValve90, state = "normal")
        self.one_button_to_rule_them_all.configure(state = "normal")
        return ClosePort(self.device_list)

    def USBCheck(self):
        "Confirm only one OtO serial card is connected"
        USB_VID = 0x10C4
        USB_PID = 0xEA60
        PortList = serial.tools.list_ports.comports()
        OtOPortList = []
        for port in PortList:
            if port.pid == USB_PID and port.vid == USB_VID:
                OtOPortList.append(port.name)
        if len(OtOPortList) > 1: # in case more than one USB card is plugged in, stop test
            return False
        else:
            return True

    def vac_interrupt(self):
        """checks vacuum switches are not triggered prior to testing"""
        if not hasattr(self.test_suite.test_devices,"gpioSuite"):
            try:
                new_gpio = GpioSuite()
                self.test_suite.test_devices.add_device(new_object = new_gpio)
            except:
                raise VacError("TEST CONTROLLER WASN'T FOUND. Is it plugged in?\n测试控制器没有找到, 是否已插入?")
        if self.test_suite.test_devices.gpioSuite.vacSwitchPin1.get() == 0 or self.test_suite.test_devices.gpioSuite.vacSwitchPin2.get() == 0 or self.test_suite.test_devices.gpioSuite.vacSwitchPin3.get() == 0:
            raise VacError("Unscrew and then retighten the black, blue and orange caps before testing again.\n黑色,蓝色和橘色瓶盖未拧紧或者未拧。测试前需拧紧。")

def ClearFigures():
    """clears all graphs and the memory associated with them"""
    plt.figure(0)
    plt.close()
    plt.figure(1)
    plt.close()
    plt.figure(2)
    plt.close()
    plt.figure(3)
    plt.close()

def ClosePort(DeviceList: TestPeripherals):
    "Closes the USB port if it is open and connected to an OtO"
    if hasattr(DeviceList, "DUTMLB"):
        if hasattr(DeviceList.DUTMLB, "connection"):
            if hasattr(DeviceList.DUTMLB.connection, "port"):
                return DeviceList.DUTMLB.stop_connection()
    return None

if __name__ == '__main__':
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # gets rid of the fuzzies on graphics display
    try:
        BOMFile = open("BOM to Flash.txt")
    except:
        msgBox.showerror(title = "BOM File Missing  缺少BOM表", message = 'Cannot find "BOM to Flash.txt" file\n未发现“BOM to Flash.txt“文件')
        quit()
    globalvars.BOMtoFlash = BOMFile.readline()
    BOMFile.close()
    if globalvars.BOMtoFlash != globalvars.KenakoreBOM and (len(globalvars.BOMtoFlash) < 6 or len(globalvars.BOMtoFlash) > 7 or globalvars.BOMtoFlash[4] != "-"):
        msgBox.showerror(title = "Invalid BOM Number  BOM 号不存在", message = globalvars.BOMtoFlash + "\nBOM must be ####-a? format\nBOM 号必须是 ####-a格式")
        quit()
    Application = MainWindow()
    Application.state('zoomed')
    Application.grid()
    Application.mainloop()
    ClearFigures()
    exit()