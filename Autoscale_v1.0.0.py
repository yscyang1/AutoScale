'''Written in python3.5, pyqt5 by Crystal Yang 2017, Siwy Group'''

import sys
import os
import serial
import time
import re
from PyQt5.QtCore import pyqtSignal, QObject, QTimer, QElapsedTimer, pyqtSlot
from PyQt5.QtWidgets import QWidget, QLabel, QMainWindow, QApplication, QPushButton, QHBoxLayout, QVBoxLayout, QFileDialog, QSizePolicy, QLineEdit, QCheckBox, QMessageBox
from PyQt5.QtGui import QDoubleValidator, QRegExpValidator

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

import winsound

# Define constants
DEFAULT_PORT = 'COM1'
DEFAULT_BAUDRATE = 9600
ESCAPE_CHAR = chr(27)
bytesize = serial.SEVENBITS
parity = serial.PARITY_NONE
stopbits = serial.STOPBITS_ONE

i_windowleft = 100
i_windowtop = 100
i_windowW = 1200
i_windowH = 600

class Gui(QMainWindow):
  def __init__(self):
    super().__init__()
    # define main window and variables callable by other classes

    self.windowtitle = 'AutoScale'
    self.windowleft = i_windowleft
    self.windowtop = i_windowtop
    self.windowW = i_windowW
    self.windowH = i_windowH

    Gui.l_mass = [0]
    Gui.l_time = [0.01]
    Gui.s_plotTitle = 'Charting Flow Rate'
    

    self.initUI()

  def initUI(self):
    # Define Gui buttons, labels, etc
    self.setGeometry(self.windowleft, self.windowtop, self.windowW, self.windowH)
    self.setWindowTitle(self.windowtitle)

    self.balance = Balance()
    self.time = Time(self.balance)
    self.plot = Plot(self, width = 12, height = 4)
    self.plot.move(0,0)

    self.count = 0
    
    startButton = QPushButton('Start', self)
    startButton.move(.1 * self.windowW, .9 * self.windowH)
    startButton.setStyleSheet('background-color: green')
    startButton.clicked.connect(self.time.startTime)
    startButton.clicked.connect(self.balance.tare)
    startButton.clicked.connect(self.plot.startPlotTime)

    stopButton = QPushButton("Stop", self)
    stopButton.move(0.3 * self.windowW, 0.9 * self.windowH)
    stopButton.setStyleSheet('background-color: red')
    stopButton.clicked.connect(self.time.stopTime)
    stopButton.clicked.connect(self.plot.stopPlotTime)

    tareButton = QPushButton("Tare", self)
    tareButton.move(0.1 * self.windowW, 0.7 * self.windowH)
    tareButton.clicked.connect(self.balance.tare)

    saveButton = QPushButton("Save", self)
    saveButton.move(0.8 * self.windowW, 0.9 * self.windowH)
    saveButton.clicked.connect(self.saveData)

    Gui.alertEdit = QLineEdit('0.1', self)
    Gui.alertEdit.move(0.2 * self.windowW, 0.79 * self.windowH)

    Gui.alertBox = QCheckBox('Alert me (g)', self)
    Gui.alertBox.resize(Gui.alertBox.sizeHint())
    Gui.alertBox.move(0.1 * self.windowW, 0.8 * self.windowH)
    Gui.alertBox.toggle()

    plotTitleEdit = QLineEdit("Enter Plot Title", self)
    plotTitleEdit.move(0.3 * self.windowW, 0.7 * self.windowH)
    plotTitleEdit.textChanged[str].connect(self.plotTitleChanged)

    Gui.samplingRateEdit = QLineEdit("Sampling rate (sec)", self)
    Gui.samplingRateEdit.move(0.5 * self.windowW, 0.9 * self.windowH)
    Gui.samplingRateEdit.editingFinished.connect(self.setSamplingRate)

    Gui.lastDataPt = QLabel("Last data point: ", self)
    Gui.lastDataPt.move(0.5 * self.windowW, 0.7 * self.windowH)

    Gui.fluxOverall = QLabel("flow rate: ", self)
    Gui.fluxOverall.move(0.8 * self.windowW, 0.7 * self.windowH)

    Gui.timerOnOff = QLabel("Timer is ", self)
    Gui.timerOnOff.move(0.22 * self.windowW, 0.9 * self.windowH)

    Time.updateTimer.timeout.connect(self.alert)

    self.show()

  def alert(self):
    if Gui.alertBox.checkState() == 2:
      if float(Gui.l_mass[-1]) > float(Gui.alertEdit.text()):
        if self.count < 1: 
          winsound.Beep(2000, 800)
          # reply = QMessageBox.information(self,"", "Target weight reached", QMessageBox.Ok)
          self.count +=1
    else:
      pass

  def saveData(self):
    # Save data
    data = self.formatData(self.l_time, self.l_mass)
    s_fileName = QFileDialog.getSaveFileName(self, 'Save File')
    s_fileName = str(s_fileName).split()[0]
    fileName = s_fileName[2:-2] + ".txt"

    
    try:
      fig = self.plot.savePlot()
      pltFileName = s_fileName[2:-2]
      print(pltFileName)
      fig.savefig(pltFileName)

      with open(fileName, 'w') as f:
        f.write(data)
        f.close()
    except ValueError:
      re1 = re.compile(r'[#%&{}\\<>.?$! \'\":@]')
      if re1.search(s_fileName[2:-2].split("/")[-1]):
        savealert = QMessageBox.information(self,"", "Possible illegal character.  File is NOT saved", QMessageBox.Ok)


    
  def formatData(self, time, mass):
    # Format data into appropriate text file format
    data = ""

    for i, datapt in enumerate(time):
      data += str(time[i]) + "\t" + str(mass[i]) + "\n"
    return data

  def plotTitleChanged(self, text):
    Gui.s_plotTitle = text

  def setSamplingRate(self):
      # sampling rate is in msec, enter as sec
     Time.samplingRate = float(Gui.samplingRateEdit.text())*1000



class Time():
# Manages all the timers, including QTimer(), which updates at regular intervals of 3000 miliseconds,
# and QElapsedTimer, which measures elasped time everytime it is called (from Qtimer's 3000 miliseconds)
  def __init__(self, balance):
    self.running = False
    Time.samplingRate = 1000
    Time.updateTimer = QTimer()
    self.elapsedTime = QElapsedTimer()

    self.balance = balance
    self.plot = Plot()


  def startTime(self):
    # Update events (graphs, labels, etc) every x millisecond, defined in setInterval()
    # Starts stopwatch (elapsedTime)
    self.updateTimer.setInterval(self.samplingRate)
    self.updateTimer.timeout.connect(self.onTimeout)
    if self.updateTimer.isActive():
      print("timer is active")
    else:
      if len(Gui.l_time) > 1:
        Gui.l_mass = [0]
        Gui.l_time = [0.01]
      print(Gui.l_time, Gui.l_mass)
      self.updateTimer.start()
      self.elapsedTime.start()
      Gui.timerOnOff.setText("Timer is ON")
      # self.alert()

  def stopTime(self):
    # Stop both timers
    Time.updateTimer.stop()
    Time.updateTimer.disconnect()
    self.elapsedTime.restart()
    Gui.timerOnOff.setText("Timer is OFF")

  def onTimeout(self):
    # After x milliseconds, update data and gui
    self.plot.addData(self.balance.read(), self.elapsedTime.elapsed()/1000)
    Gui.lastDataPt.setText("last data point: {0} sec, {1} g".format(str(Gui.l_time[-1]), str(Gui.l_mass[-1])))
    Gui.lastDataPt.adjustSize()
    microL = float(Gui.l_mass[-1]) * 1000
    minute = float(Gui.l_time[-1]) / 60
    flowRate = format(microL / minute,'.2f')
    Gui.fluxOverall.setText(str(flowRate) + " uL/min")
    Gui.fluxOverall.adjustSize()



class Balance():
# Communicates with the Balance.  
  def __init__(self):
    self.ser = serial.Serial()
    self.ser.baudrate = DEFAULT_BAUDRATE
    self.ser.port = DEFAULT_PORT
    self.ser.open()


  def tare(self):
    # Tare device
    self.ser.write((ESCAPE_CHAR + 'T').encode())

  # @pyqtSlot()
  def read(self):
    # Read weight 
    self.ser.write((ESCAPE_CHAR + 'P').encode())
    weight = self.ser.readline(30)

    s_weight = weight.split()[0].decode('utf-8')
    if s_weight == "-":
      s_weight += weight.split()[1].decode('utf-8')
    
    return s_weight



class Plot(Gui, Time, FigureCanvas):
  # why does program go through Plot() twice?
  def __init__(self, parent = None, width = 12, height = 4, dpi = 100):
    fig = Figure(figsize = (width, height), dpi = dpi)
    self.fig = fig
    self.axes = fig.add_subplot(111)
    self.axes.hold(False)

    FigureCanvas.__init__(self, fig)
    self.setParent(parent)

    FigureCanvas.setSizePolicy(self,
      QSizePolicy.Expanding,
      QSizePolicy.Expanding)
    FigureCanvas.updateGeometry(self)

    self.updatePlotTimer = QTimer()
    self.elapsedPlotTimer = QElapsedTimer()


  def startPlotTime(self):
    self.updatePlotTimer.setInterval(1000)
    self.updatePlotTimer.timeout.connect(self.drawPlot)

    if self.updatePlotTimer.isActive():
      print('plot timer is active')
    else:
      self.updatePlotTimer.start()
      self.elapsedPlotTimer.start()
      print(Gui.l_time)
      # print("timer id: {}".format(self.updatePlotTimer.timerId()))

  def stopPlotTime(self):
    self.updatePlotTimer.stop()
    self.updatePlotTimer.disconnect()
    self.elapsedPlotTimer.restart()

  def drawPlot(self):
    data = [Gui.l_time, Gui.l_mass]
    # print("time: {}, mass: {}".format(Gui.l_time, Gui.l_mass))
    ax = self.figure.add_subplot(111)
    ax.plot(Gui.l_time, Gui.l_mass, 'or-')
    ax.set_title(Gui.s_plotTitle)
    ax.set_xlabel("time (seconds)")
    ax.set_ylabel("mass (g)")
    self.fig.canvas.draw()
    self.fig.canvas.flush_events()
    self.fig.tight_layout()
    ax.grid(True)
    self.draw()


  def addData(self, mass, time):
    Gui.l_mass.append(mass)
    Gui.l_time.append(time)
 
  def savePlot(self):
    return self.fig
  

if __name__ == '__main__':
  app = QApplication(sys.argv)
  scale = Gui()
  sys.exit(app.exec_())
  ser.close()

