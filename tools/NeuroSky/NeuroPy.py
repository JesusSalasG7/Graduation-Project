import serial
import threading
import time

class NeuroPy(object):
    def __init__(self, port, baudRate=57600):
        self.port = port
        self.baudRate = baudRate
        self.monitor = None
        self.srl = None
        self.running = False
        
        self.attention = 0
        self.meditation = 0
        self.rawValue = 0
        self.delta = 0
        self.theta = 0
        self.lowAlpha = 0
        self.highAlpha = 0
        self.lowBeta = 0
        self.highBeta = 0
        self.lowGamma = 0
        self.midGamma = 0
        self.poorSignal = 0
        self.blinkStrength = 0

        self.callBacksDictionary = {}

    def start(self):
        self.running = True
        self.srl = serial.Serial(self.port, self.baudRate)
        self.monitor = threading.Thread(target=self.__packetParser)
        self.monitor.setDaemon(True)
        self.monitor.start()

    def stop(self):
        self.running = False
        if self.monitor:
            self.monitor.join(timeout=1.0)
        if self.srl:
            self.srl.close()

    def setCallBack(self, variable_name, callback_function):
        self.callBacksDictionary[variable_name] = callback_function

    def __packetParser(self):
        while self.running:
            try:
                # Sincronización: Buscar bytes de inicio [0xAA, 0xAA]
                b1 = int(self.srl.read(1).hex(), 16)
                if b1 == 0xAA:
                    b2 = int(self.srl.read(1).hex(), 16)
                    if b2 == 0xAA:
                        # Payload Length
                        pLength = int(self.srl.read(1).hex(), 16)
                        if pLength > 169: continue

                        payload = self.srl.read(pLength)
                        checksum = int(self.srl.read(1).hex(), 16)
                        
                        generated_checksum = sum(payload) & 0xFF
                        generated_checksum = ~generated_checksum & 0xFF

                        if checksum == generated_checksum:
                            self.__parsePayload(payload)
            except Exception as e:
                # Manejo suave de errores seriales para no romper el hilo
                pass

    def __parsePayload(self, payload):
        bytesParsed = 0
        while bytesParsed < len(payload):
            code = payload[bytesParsed]
            bytesParsed += 1
            
            # --- Extended Code Level ---
            while code == 0x55: # EXCODE
                code = payload[bytesParsed]
                bytesParsed += 1

            if code == 0x02: # POOR SIGNAL
                self.poorSignal = payload[bytesParsed]
                bytesParsed += 1
                if 'poorSignal' in self.callBacksDictionary:
                    self.callBacksDictionary['poorSignal'](self.poorSignal)
            
            elif code == 0x04: # ATTENTION
                self.attention = payload[bytesParsed]
                bytesParsed += 1
                if 'attention' in self.callBacksDictionary:
                    self.callBacksDictionary['attention'](self.attention)
            
            elif code == 0x05: # MEDITATION
                self.meditation = payload[bytesParsed]
                bytesParsed += 1
                if 'meditation' in self.callBacksDictionary:
                    self.callBacksDictionary['meditation'](self.meditation)
            
            elif code == 0x16: # BLINK
                self.blinkStrength = payload[bytesParsed]
                bytesParsed += 1
                if 'blinkStrength' in self.callBacksDictionary:
                    self.callBacksDictionary['blinkStrength'](self.blinkStrength)

            elif code == 0x80: # RAW WAVE (2 bytes)
                # length = payload[bytesParsed] # Should be 2
                bytesParsed += 1 
                val0 = payload[bytesParsed]
                val1 = payload[bytesParsed+1]
                self.rawValue = val0 * 256 + val1
                if self.rawValue >= 32768:
                    self.rawValue = self.rawValue - 65536
                bytesParsed += 2
                if 'rawValue' in self.callBacksDictionary:
                    self.callBacksDictionary['rawValue'](self.rawValue)

            elif code == 0x83: # ASIC EEG POWER (24 bytes - All Bands)
                # length = payload[bytesParsed] # Should be 24
                bytesParsed += 1 
                
                # Función auxiliar para leer 3 bytes big-endian
                def read3(idx):
                    return (payload[idx] << 16) | (payload[idx+1] << 8) | payload[idx+2]

                self.delta = read3(bytesParsed)
                self.theta = read3(bytesParsed+3)
                self.lowAlpha = read3(bytesParsed+6)
                self.highAlpha = read3(bytesParsed+9)
                self.lowBeta = read3(bytesParsed+12)
                self.highBeta = read3(bytesParsed+15)
                self.lowGamma = read3(bytesParsed+18)
                self.midGamma = read3(bytesParsed+21)
                
                bytesParsed += 24
                
                # Disparamos callbacks si existen
                for band in ['delta', 'theta', 'lowAlpha', 'highAlpha', 'lowBeta', 'highBeta', 'lowGamma', 'midGamma']:
                    if band in self.callBacksDictionary:
                        self.callBacksDictionary[band](getattr(self, band))
            else:
                # Unknown code, skip its length if possible, but mostly just exit loop safely
                # Normalmente no deberíamos caer aquí si los paquetes son estándar
                pass
