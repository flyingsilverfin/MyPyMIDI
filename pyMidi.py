
class Note():
	def __init__(self, noteId):
		self.id = noteId
	def getId(self):
		return self.id
	

class ActiveNotes():
	def __init__(self, outputFile):
		self.activenotes = []
		self.outfile = outputFile
	def setFile(self, outputFile):
		self.outfile.close()
		self.outfile = outputFile
	def clear(self, dt):
		time = dt/1000000
		if time < 0.0000001: #too small, shows up as 0 in print (probably not necessary)
			activeNotes = []
			return
		if len(self.activenotes) == 0:
			self.outfile.write("\nNone %.2f" %time)
			return
		self.outfile.write("\n"+idConversion[self.activenotes[0].getId()] + " %.2f " %(time) + " ".join([idConversion[note.getId()] for note in self.activenotes[1:]]))
		self.activenotes = []
	def addNote(self, note):
		self.activenotes.append(note)
		if not silenced: 
			print [note.getId() for note in self.activenotes]
	def end(self, procForMathematica):
		loc = self.outfile.name
		self.outfile.close()
		if procForMathematica:
			self.processForMathematica(loc)

	def processForMathematica(self,fileLoc):
		f = open(fileLoc)
		data = f.readlines()
		if len(data) == 0:
			return;
		del(data[0])
		f.close()
		f = open(fileLoc+"_MATHEMATICA_OUT.txt",'w')
		f.write("{")
		for x in range(0,len(data)-1):
			d = data[x].split(" ")
			d[-1] = d[-1].rstrip()
			if d[-1] == '':
				del(d[-1])
			if len(d) <= 2:
				if "None" in d[0]:
					notes = d[0]
				else:
					notes = "\"" + d[0] + "\""
			else:
				notes = "\"" + d[0] + "\",\"" + "\",\"".join(d[2:]) + "\""
			time = d[1].rstrip()
			f.write("{{" + notes + "}," + time + "},")
		d = data[-1].split(" ")
		d[-1] = d[-1].rstrip()
		if d[-1] == '':
			del(d[-1])
		if len(d) <= 2:
			notes = "\"" + d[0] + "\""
		else:
			notes = "\"" + d[0] + "\",\"" + "\",\"".join(d[2:]) + "\""
		time = d[1].rstrip()
		f.write("{{" + notes + "}," + time + "}}")
		f.close()
		print("Check location of input file for output!")
	
	def isEmpty(self):
		if len(self.activenotes) > 0:
			return False
		else:
			return True
			
			
			


class MidiConverter():
	def __init__(self, inputFileLoc, outputFileLoc, fractionOfQNoteAsThreshold):
		midifile = open(inputFileLoc, "rb")
		self.data = []
		while True:
			d = midifile.read(1)
			if d == '':
				break
			self.data.append(ord(d)) #convert to numbers and save
		midifile.close()
		self.outfile_loc = outputFileLoc
		self.NOTE_LEN_ROUNDING_FRACTION = fractionOfQNoteAsThreshold
		
		self.header = self.getHeader(self.data)
		self.format = self.getFormat(self.header)
		print "Format: %s" %self.format
		self.num_tracks = self.getNumTracks(self.header)
		self.ticks_per_quarter_note = self.getTicksPerQuarterNote(self.header)
		print "Number of tracks: %d" %self.num_tracks
		if not silenced: 
			print "ticks per quarter note: %d" %self.ticks_per_quarter_note

		#header length should always be 14 for current spec
	def getHeader(self,data):
		return data[:14]
		
	def getFormat(self, header):
		return 256*header[8] + header[9]
		
	def getNumTracks(self, header):
		return 256*header[10] + header[11]
		
	def getTicksPerQuarterNote(self, header):
		if header[12] > 128:
			if not silenced: 
				print "cannot handle 1 as MSB for delta-time"
			return -1
		return (header[12] << 8) + header[13]

	#extract track header at position 
	#track length always 8 bytes
	def getTrackHeader(self, data, position):
		tmp = data[position:position+8]
		if tmp[:4] != [ord("M"), ord("T"), ord("r"), ord("k")]:
			if not silenced: 
				print "WARNING: given position doesn't seem to be beginning of a track"
			if not silenced: 
				print "\tposition: %d" %position
		return tmp
		
	def getTrackLength(self, trackHeader):
		#return length of track from the 4 bytes
		return (trackHeader[4] << 8*3) + (trackHeader[5] << 8*2) + (trackHeader[6] << 8) + trackHeader[7]
		
	
	def parseMidiFile(self, mathematicaCompat = False):
		position_counter = len(self.header) #skip the header
		outfile = open(self.outfile_loc + "_track1.txt", 'w')
		self.active_notes_pool = ActiveNotes(outfile)	#create active notes container
		self.micros_per_qnote = 1	#holder value, should be updated from meta in first track
		self.last_event = -1		#holder value
		offset = position_counter
		self.track_length = 0
		for i in range(self.num_tracks):
			outfile = open(self.outfile_loc + "_track%d.txt" %(i+1), 'w')
			self.active_notes_pool.setFile(outfile)
			self.in_track = True #flag can be toggled from event parsers
			self.track_length += self.getTrackLength(self.getTrackHeader(self.data, position_counter)) #have to do += to account for previous tracks etc
			if not silenced: 
				print "----- NEW TRACK ----- "
			if not silenced: 
				print "\t--Track %d length: %d--" %(i+1, self.track_length)
			
			position_counter += 8	#length of track header
			offset += 8		#save difference
			self.dt = 0
			self.accumulate_dt = True
			while self.in_track and position_counter < self.track_length + offset:
				if not silenced: 
					print "Pos: " + str(position_counter)
				timeVarLen = self.getLenVariableQuantity(self.data, position_counter)

				if self.accumulate_dt:
					tmp = self.getLength(self.data, position_counter)
					if not silenced: 
						print tmp
					self.dt += tmp * (1/float(self.ticks_per_quarter_note)) * self.micros_per_qnote #add new timestamp
					if not silenced: 
						print "\tACCUMULATING: total = %6f" %(self.dt/1000000)

				else:
					self.dt = self.getLength(self.data, position_counter)
					if not silenced: 
						print "\tThis time: %6f ticks"  %(self.dt)
					self.dt = self.dt * (1/float(self.ticks_per_quarter_note)) * self.micros_per_qnote #set new timestamp
				if not silenced: 
					print "\tTotal Time: " + str(self.dt/1000000)
				#print "\tTime: " + str([hex(s) for s in self.data[position_counter:position_counter+timeVarLen]])
				if not silenced: 
					print "\tCom: " + hex(self.data[position_counter+timeVarLen])
				position_counter += timeVarLen
				
				position_counter += self.handle(self.data, position_counter, self.dt)
				if not silenced: 
					print ""
			self.active_notes_pool.end(mathematicaCompat)
	
	#returns number of variable length bytes found
	def getLenVariableQuantity(self, data, position):
		l = 1
		counter = 0
		while data[position+counter] >= 128:
			l += 1
			counter += 1
		return l
	
	#returns length indicated by variable length bytes
	#length starts counting after the last variable len byte
	#number accessible via getLenVariableQuantity
	def getLength(self, data, position):
		length = 0
		counter = 0
		num = self.getLenVariableQuantity(data, position)
		for i in range(0, num-1):
			length += (data[i+position]-128) << (7*(num-1-i))
		length += data[position+num-1]
		return length
		
		
	def handle(self, data, position, dt):
		if data[position] == 255:
			self.accumulate_dt = True
			return self.handleMetaEvent(data, position)
		elif data[position] >= 128 and data[position] < 240: #between 240 and 255 are reserved for system somethings
			#self.accumulate_dt = False #setting this inside handle midi event
			return self.handleMidiEvent(data, position, dt)
		elif data[position] >= 240 and data[position] < 255:
			self.accumulate_dt = True
			return self.handleSystemEvent(data, position)
		elif data[position] < 128:	#running status
			tmp = self.handleMidiEvent(data, position, dt, runningStatus = True)
			self.accumulate_dt = False	#set afterward to override whatever was set inside
			return tmp

			

	def handleMetaEvent(self, data, meta_position):
		metaType = data[meta_position+1]	#first byte is FF, second is type code
		dataLength = self.getLength(data, meta_position+2)	#next bytes are variable len bytes indicating length of data
		startDataPosition = meta_position + 2 + self.getLenVariableQuantity(data, meta_position+2)
		d = data[startDataPosition : startDataPosition + dataLength]
		if metaType == 0:	#sequence number
			if not silenced: 
				print "\tSequence number: %s" %"".join([chr(n) for n in d])
			
		elif metaType == 1: #text event
			if not silenced: 
				print "".join([chr(n) for n in d])
			
		elif metaType == 2:	#copyright notice
			if not silenced: 
				print "\tCopyright notice: %s" %"".join([chr(n) for n in d])
			
		elif metaType == 3: #name of sequence or track
			if not silenced: 
				print "\tTrack/sequence name: %s" %"".join([chr(n) for n in d])
			
		elif metaType == 4: #instrument name for this track
			if not silenced: 
				print "\tInstrument: %s" %"".join([chr(n) for n in d])
			
		elif metaType == 5: #lyrics; normally each syllable will have it's own lyric event
							#ocurring at each time the lyric is to be sung
			if not silenced: 
				print "\t[lyric]: %s" %"".join([chr(n) for n in d])
			
		elif metaType == 6: #marker (significant point eg "verse 1")
			if not silenced: 
				print "\t[marker]: %s" %"".join([chr(n) for n in d])
			
		elif metaType == 7: #cue point (eg "curtain rises")
			if not silenced: 
				print "\t*%s*" %"".join([chr(n) for n in d])
			
		elif metaType == 20:	#Channel Prefix "
		#-->Associate all following meta-events and sysex-events with the specified MIDI channel, until the next <midi_event> (which must contain MIDI channel information). "
			if not silenced: 
				print "\tChannel prefix: %s" %"".join([chr(n) for n in d])

		elif metaType == 47:	#end of track (20xF)
			if not silenced: 
				print "END OF TRACK"
			self.in_track = False	#break out of track loop
			return 3
			
		elif metaType == 81:	#set tempo (0x51)
			if not silenced: 
				print "\tSETTING TEMPO"
			#data will always be length 3 for tempo
			self.micros_per_qnote = (d[0] << 2*8) + (d[1] << 8) + (d[2])
			self.NOTE_LEN_ROUNDING_THRESHOLD = float(self.NOTE_LEN_ROUNDING_FRACTION) * self.micros_per_qnote
			if not silenced: 
				print "\t\tMicroseconds per quarter note: %d" %self.micros_per_qnote
			if not silenced: 
				print "\t\tRounding threshold: %f, this is %f of a quarter note" %(self.NOTE_LEN_ROUNDING_THRESHOLD, self.NOTE_LEN_ROUNDING_FRACTION)

		elif metaType == 84:	#SMTPE offset (0x54)
			if not silenced: 
				print "\tSMPTE something..."
		
		elif metaType == 88:	#time signature (0x58)
			if not silenced: 
				print "\tSETTING TIME SIG"
			self.timesig_numerator = d[0]
			self.timesig_denominator = d[1] #2 = quarter, 3 = eigth etc
			self.ticks_per_metronometick = d[2]
			self.thirtysecondnotes_per_qnote = d[3] #what's this used for?
			if not silenced: 
				print "\t\t%d/%d, %d ticks/metronome tick, %d 32nd notes per quarter note" %(d[0],
																d[1], d[2], d[3])			
		
		elif metaType == 89:	#key signature (0x59)
			if not silenced: 
				print "\tSETTING KEY SIG"
			if d[0] < 0:
				self.num_sharps = abs(d[0])
				self.num_flats = 0
				if not silenced: 
					print "\t\tNumber of sharps: %d" %self.num_sharps
			elif d[0] == 0:
				self.num_sharps = 0
				self.num_flats = 0
				if not silenced: 
					print "\t\tKey is C, no sharps/flats"
			else:
				self.num_sharps = 0
				self.num_flats = d[0]
				if not silenced: 
					print "\t\tNumber of flats: %d" %self.num_flats
			self.is_major = True if d[2] == 0 else False
			if not silenced: 
				print "\t\tThis is " + "major" if self.is_major else "minor"
		
		elif metaType == 127:	#sequencer-specific meta event (0x7F)
			if not silenced: 
				print "\tSequence specific meta key... (?)"
		
		#return number of bytes to skip, whether command known or unknown
		return dataLength + 3 #length of data + FF + type + len
		
		

	#returns number of bytes used by this event
	def handleMidiEvent(self, data, position, dTSinceLastTurnOn, runningStatus = False):
		command = data[position]
		event = command >> 4
		channel = command & 0b00001111
		
		if runningStatus == True:
			event = self.last_event

		toReturn = 0
		
		if event == 8:	#note off (0b1000)
			if not silenced: 
				print "\tNote off"
			self.accumulate_dt = False
			noteNumber = data[position+1] #MSB is always 0
			velocity = data[position+2]
			self.active_notes_pool.clear(dTSinceLastTurnOn)	
			self.last_event = 8
			toReturn = 3
		elif event == 9:	#note on (0b1001)
			self.accumulate_dt = False
			if runningStatus:
				noteNumber = data[position]
				velocity = data[position+1]
			else:
				noteNumber = data[position+1]
				velocity = data[position+2]
			if not silenced: 
				print "\tVelocity = " + str(velocity), 
			if velocity == 0:	#if this is an implicit NOTE OFF
				if not silenced: 
					print " -> clearing notes "
				self.active_notes_pool.clear(dTSinceLastTurnOn)
			else:				#if not
				if dTSinceLastTurnOn > self.NOTE_LEN_ROUNDING_THRESHOLD and not self.active_notes_pool.isEmpty(): #feels like a hack
					if not silenced: 
						print " clearing notes, difference large enough!"
					self.active_notes_pool.clear(dTSinceLastTurnOn)
				self.active_notes_pool.addNote(Note(noteNumber))
				if not silenced: 
					print "\tNote on is: " + idConversion[noteNumber]
			"""				
			
			if velocity == 0 and dTSinceLastTurnOn > self.NOTE_LEN_ROUNDING_THRESHOLD:
				if not silenced: 
print str(dTSinceLastTurnOn) + " is less than rounding threshold " + str(self.NOTE_LEN_ROUNDING_THRESHOLD)
				if not silenced: 
print "->OFF. Clearing"
				self.active_notes_pool.clear(dTSinceLastTurnOn)
			elif velocity > 0 and dTSinceLastTurnOn <= self.NOTE_LEN_ROUNDING_THRESHOLD:
				self.active_notes_pool.addNote(Note(noteNumber))
				if not silenced: 
print "\tNote on is: " + idConversion[noteNumber]
			"""
			self.last_event = 9
			toReturn = 3
		elif event == 10:	#Aftertouch (0b1010)
			self.accumulate_dt = True
			noteNumber = data[position+1] #MSB is always 0
			velocity = data[position+2]
			if not silenced: 
				print "\tAftertouch... [unsupported]"
			self.last_event = 10
			toReturn = 3
		elif event == 11:	#control change (0b1011)
			self.accumulate_dt = True
			if not silenced: 
				print "\tControl change... [unsupported]"
			controllerNumber = data[position+1]
			value = data[position+2]
			self.last_event = 11
			toReturn = 3
		elif event == 12:	#Program change (0b1100)
			self.accumulate_dt = True
			prgraom = data[position+1]
			if not silenced: 
				print "\tProgram change... [unsupported]"
			self.last_event = 12
			toReturn = 2
		elif event == 13:	#Channel pressure (?) (0b1101)
			self.accumulate_dt = True
			bottomBits = data[position+1]
			topBits = data[position+1]
			if not silenced: 
				print "\tChannel pressure... [unsupported]"
			self.last_event = 13
			toReturn = 3
		else:
			self.accumulate_dt = False
			if not silenced: 
				print "\tSome unkown Midi command..."
			if not silenced: 
				print "\tSkipping 3 bytes"
			toReturn = 3
		if runningStatus == True:
			return toReturn - 1
		else:
			return toReturn
		
	#returns number of bytes used by this event
	def handleSystemEvent(self, data, position):
		event = data[position]
		if event == 248:	#0xF8
			if not silenced: 
				print "supposed to do something with toggling timing clock for synchronization... [unsupported]"
		
		elif event == 251:	#0xFA
			if not silenced: 
				print "supposed to start current sequence... [unsupported]"
		
		elif event == 252:	#0xFB
			if not silenced: 
				print "supposed to continue a stopped sequence... [unsupported]"
		
		elif event == 253:	#0xFC
			if not silenced: 
				print "supposed to stop a sequence... [unsupported]"
		return 1

		
if __name__ == "__main__":
	silenced = True

	#idConversion = {0: 'C0', 1: 'CSHARP0', 2: 'D0', 3: 'DSHARP0', 4: 'E0', 5: 'F0', 6: 'FSHARP0', 7: 'G0', 8: 'GSHARP0', 9: 'A0', 10: 'ASHARP0', 11: 'B0', 12: 'C1', 13: 'CSHARP1', 14: 'D1', 15: 'DSHARP1', 16: 'E1', 17: 'F1', 18: 'FSHARP1', 19: 'G1', 20: 'GSHARP1', 21: 'A1', 22: 'ASHARP1', 23: 'B1', 24: 'C2', 25: 'CSHARP2', 26: 'D2', 27: 'DSHARP2', 28: 'E2', 29: 'F2', 30: 'FSHARP2', 31: 'G2', 32: 'GSHARP2', 33: 'A2', 34: 'ASHARP2', 35: 'B2', 36: 'C3', 37: 'CSHARP3', 38: 'D3', 39: 'DSHARP3', 40: 'E3', 41: 'F3', 42: 'FSHARP3', 43: 'G3', 44: 'GSHARP3', 45: 'A3', 46: 'ASHARP3', 47: 'B3', 48: 'C4', 49: 'CSHARP4', 50: 'D4', 51: 'DSHARP4', 52: 'E4', 53: 'F4', 54: 'FSHARP4', 55: 'G4', 56: 'GSHARP4', 57: 'A4', 58: 'ASHARP4', 59: 'B4', 60: 'C5', 61: 'CSHARP5', 62: 'D5', 63: 'DSHARP5', 64: 'E5', 65: 'F5', 66: 'FSHARP5', 67: 'G5', 68: 'GSHARP5', 69: 'A5', 70: 'ASHARP5', 71: 'B5', 72: 'C6', 73: 'CSHARP6', 74: 'D6', 75: 'DSHARP6', 76: 'E6', 77: 'F6', 78: 'FSHARP6', 79: 'G6', 80: 'GSHARP6', 81: 'A6', 82: 'ASHARP6', 83: 'B6', 84: 'C7', 85: 'CSHARP7', 86: 'D7', 87: 'DSHARP7', 88: 'E7', 89: 'F7', 90: 'FSHARP7', 91: 'G7', 92: 'GSHARP7', 93: 'A7', 94: 'ASHARP7', 95: 'B7', 96: 'C8', 97: 'CSHARP8', 98: 'D8', 99: 'DSHARP8', 100: 'E8', 101: 'F8', 102: 'FSHARP8', 103: 'G8', 104: 'GSHARP8', 105: 'A8', 106: 'ASHARP8', 107: 'B8', 108: 'C9', 109: 'CSHARP9', 110: 'D9', 111: 'DSHARP9', 112: 'E9', 113: 'F9', 114: 'FSHARP9', 115: 'G9', 116: 'GSHARP9', 117: 'A9', 118: 'ASHARP9', 119: 'B9', 120: 'C10', 121: 'CSHARP10', 122: 'D10', 123: 'DSHARP10', 124: 'E10', 125: 'F10', 126: 'FSHARP10', 127: 'G10', 128: 'GSHARP10', 129: 'A10', 130: 'ASHARP10', 131: 'B10'}
	idConversion = {0: 'C-1', 1: 'CSHARP-1', 2: 'D-1', 3: 'DSHARP-1', 4: 'E-1', 5: 'F-1', 6: 'FSHARP-1', 7: 'G-1', 8: 'GSHARP-1', 9: 'A-1', 10: 'ASHARP-1', 11: 'B-1', 12: 'C0', 13: 'CSHARP0', 14: 'D0', 15: 'DSHARP0', 16: 'E0', 17: 'F0', 18: 'FSHARP0', 19: 'G0', 20: 'GSHARP0', 21: 'A0', 22: 'ASHARP0', 23: 'B0', 24: 'C1', 25: 'CSHARP1', 26: 'D1', 27: 'DSHARP1', 28: 'E1', 29: 'F1', 30: 'FSHARP1', 31: 'G1', 32: 'GSHARP1', 33: 'A1', 34: 'ASHARP1', 35: 'B1', 36: 'C2', 37: 'CSHARP2', 38: 'D2', 39: 'DSHARP2', 40: 'E2', 41: 'F2', 42: 'FSHARP2', 43: 'G2', 44: 'GSHARP2', 45: 'A2', 46: 'ASHARP2', 47: 'B2', 48: 'C3', 49: 'CSHARP3', 50: 'D3', 51: 'DSHARP3', 52: 'E3', 53: 'F3', 54: 'FSHARP3', 55: 'G3', 56: 'GSHARP3', 57: 'A3', 58: 'ASHARP3', 59: 'B3', 60: 'C4', 61: 'CSHARP4', 62: 'D4', 63: 'DSHARP4', 64: 'E4', 65: 'F4', 66: 'FSHARP4', 67: 'G4', 68: 'GSHARP4', 69: 'A4', 70: 'ASHARP4', 71: 'B4', 72: 'C5', 73: 'CSHARP5', 74: 'D5', 75: 'DSHARP5', 76: 'E5', 77: 'F5', 78: 'FSHARP5', 79: 'G5', 80: 'GSHARP5', 81: 'A5', 82: 'ASHARP5', 83: 'B5', 84: 'C6', 85: 'CSHARP6', 86: 'D6', 87: 'DSHARP6', 88: 'E6', 89: 'F6', 90: 'FSHARP6', 91: 'G6', 92: 'GSHARP6', 93: 'A6', 94: 'ASHARP6', 95: 'B6', 96: 'C7', 97: 'CSHARP7', 98: 'D7', 99: 'DSHARP7', 100: 'E7', 101: 'F7', 102: 'FSHARP7', 103: 'G7', 104: 'GSHARP7', 105: 'A7', 106: 'ASHARP7', 107: 'B7', 108: 'C8', 109: 'CSHARP8', 110: 'D8', 111: 'DSHARP8', 112: 'E8', 113: 'F8', 114: 'FSHARP8', 115: 'G8', 116: 'GSHARP8', 117: 'A8', 118: 'ASHARP8', 119: 'B8', 120: 'C9', 121: 'CSHARP9', 122: 'D9', 123: 'DSHARP9', 124: 'E9', 125: 'F9', 126: 'FSHARP9', 127: 'G9', 128: 'GSHARP9', 129: 'A9', 130: 'ASHARP9', 131: 'B9'}
	midiRead = MidiConverter("C:\\Users\\Joshua Send\\Desktop\\Chopop28\\chopop28.mid", "C:\\Users\\Joshua Send\\Desktop\\Chopop28\\results_chopop28", 1/32.0)
	midiRead.parseMidiFile(mathematicaCompat=True)
