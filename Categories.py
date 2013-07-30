import wx
import re
import Model
import Utils
from Undo import undo
import wx.grid			as gridlib
import wx.lib.masked	as  masked

from GetResults import GetCategoryDetails
from ExportGrid import ExportGrid

#--------------------------------------------------------------------------------

class CategoriesPrintout( wx.Printout ):
    def __init__(self, categories = None):
		wx.Printout.__init__(self)

    def OnBeginDocument(self, start, end):
        return super(CategoriesPrintout, self).OnBeginDocument(start, end)

    def OnEndDocument(self):
        super(CategoriesPrintout, self).OnEndDocument()

    def OnBeginPrinting(self):
        super(CategoriesPrintout, self).OnBeginPrinting()

    def OnEndPrinting(self):
        super(CategoriesPrintout, self).OnEndPrinting()

    def OnPreparePrinting(self):
        super(CategoriesPrintout, self).OnPreparePrinting()

    def HasPage(self, page):
		return page == 1

    def GetPageInfo(self):
		return (1,1,1,1)

    def OnPrintPage(self, page):
		race = Model.race
		if not race:
			return
			
		catDetails = GetCategoryDetails()
		
		title = '\n'.join( ['Categories', race.name, race.scheduledStart + ' Start on ' + Utils.formatDate(race.date)] )
		colnames = ['Start Time', 'Category', 'Gender', 'Numbers', 'Laps', 'Distance']
		
		raceStart = Utils.StrToSeconds( race.scheduledStart + ':00' )
		catData = []
		for c in race.getCategories():
			catInfo = catDetails.get( c.fullname, {} )
			laps = c.numLaps
			if laps:
				raceDistance = '%.2f' % c.getDistanceAtLap( laps )
			else:
				laps = catInfo.get( 'laps', '' )
				if laps:
					raceDistance = '%.2f' % c.getDistanceAtLap( laps )
				else:
					raceDistance = ''
					laps = ''
				
			catData.append( [
				Utils.SecondsToStr( raceStart + c.getStartOffsetSecs() ),
				c.name,
				catInfo.get('gender', 'Open'),
				c.catStr,
				str(laps),
				' '.join([raceDistance, race.distanceUnitStr]) if raceDistance else ''
			])
			
		catData.sort( key = lambda d: (Utils.StrToSeconds(d[0]), d[1]) )
		
		data = [[None] * len(catData) for i in xrange(len(colnames))]
		for row in xrange(len(catData)):
			for col in xrange(len(colnames)):
				data[col][row] = catData[row][col]
				
		exportGrid = ExportGrid( title = title, colnames = colnames, data = data )
		exportGrid.leftJustifyCols = set([1, 2, 3])
		exportGrid.drawToFitDC( self.GetDC() )
		return True

#--------------------------------------------------------------------------------
class TimeEditor(gridlib.PyGridCellEditor):
	def __init__(self):
		self._tc = None
		self.startValue = '00:00:00'
		gridlib.PyGridCellEditor.__init__(self)
		
	def Create( self, parent, id, evtHandler ):
		self._tc = masked.TimeCtrl( parent, id, style=wx.TE_CENTRE, fmt24hr=True, displaySeconds = True, value = '00:00:00' )
		self.SetControl( self._tc )
		if evtHandler:
			self._tc.PushEventHandler( evtHandler )
	
	def SetSize( self, rect ):
		self._tc.SetDimensions(rect.x, rect.y, rect.width+2, rect.height+2, wx.SIZE_ALLOW_MINUS_ONE )
	
	def BeginEdit( self, row, col, grid ):
		self.startValue = grid.GetTable().GetValue(row, col)
		self._tc.SetValue( self.startValue )
		self._tc.SetFocus()
		
	def EndEdit( self, row, col, grid ):
		changed = False
		val = self._tc.GetValue()
		if val != self.startValue:
			change = True
			grid.GetTable().SetValue( row, col, val )
		self.startValue = '00:00:00'
		self._tc.SetValue( self.startValue )
		
	def Reset( self ):
		self._tc.SetValue( self.startValue )
		
	def Clone( self ):
		return TimeEditor()

class CustomEnumRenderer(gridlib.PyGridCellRenderer):
	def __init__(self, choices):
		self.choices = choices.split( ',' )
		gridlib.PyGridCellRenderer.__init__(self)

	def Draw(self, grid, attr, dc, rect, row, col, isSelected):
		value = grid.GetCellValue( row, col )
		try:
			value = self.choices[int(value)]
		except (ValueError, IndexError):
			pass
			
		dc.SetClippingRect( rect )
		dc.SetBackgroundMode(wx.SOLID)
		dc.SetBrush(wx.WHITE_BRUSH)
		dc.SetPen(wx.TRANSPARENT_PEN)
		dc.DrawRectangleRect(rect)
		
		dc.SetTextForeground(wx.BLACK)
		dc.SetPen( wx.BLACK_PEN )
		dc.SetFont( attr.GetFont() )
		
		w, h = dc.GetTextExtent( value )
		
		x = int((rect.GetWidth() - w) / 2) if w < rect.GetWidth() else 2
		y = int((rect.GetHeight() - h) / 2) if h < rect.GetHeight() else 2
		
		dc.DrawText(value, rect.x + x, rect.y + y)
		dc.DestroyClippingRegion()

	def GetBestSize(self, grid, attr, dc, row, col):
		text = grid.GetCellValue(row, col)
		dc.SetFont(attr.GetFont())
		w, h = dc.GetTextExtent(text)
		return wx.Size(w, h)


	def Clone(self):
		return CustomEnumRenderer()
		
#--------------------------------------------------------------------------------
class Categories( wx.Panel ):
	def __init__( self, parent, id = wx.ID_ANY ):
		wx.Panel.__init__(self, parent, id)
		
		vs = wx.BoxSizer( wx.VERTICAL )
		
		border = 4
		flag = wx.ALL
		
		hs = wx.BoxSizer( wx.HORIZONTAL )
		
		self.newCategoryButton = wx.Button(self, id=wx.ID_ANY, label='&New Category', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onNewCategory, self.newCategoryButton )
		hs.Add( self.newCategoryButton, 0, border = border, flag = flag )
		
		self.delCategoryButton = wx.Button(self, id=wx.ID_ANY, label='&Delete Category', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onDelCategory, self.delCategoryButton )
		hs.Add( self.delCategoryButton, 0, border = border, flag = flag )

		hs.AddSpacer( 10 )
		
		self.upCategoryButton = wx.Button(self, id=wx.ID_ANY, label='&Up', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onUpCategory, self.upCategoryButton )
		hs.Add( self.upCategoryButton, 0, border = border, flag = flag )

		self.downCategoryButton = wx.Button(self, id=wx.ID_ANY, label='D&own', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onDownCategory, self.downCategoryButton )
		hs.Add( self.downCategoryButton, 0, border = border, flag = (flag & ~wx.LEFT) )

		hs.AddSpacer( 10 )
		
		self.addExceptionsButton = wx.Button(self, id=wx.ID_ANY, label='&Add Bib Exceptions', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onAddExceptions, self.addExceptionsButton )
		hs.Add( self.addExceptionsButton, 0, border = border, flag = (flag & ~wx.LEFT) )

		hs.AddStretchSpacer()
		
		self.printButton = wx.Button( self, id=wx.ID_ANY, label='Print...', style=wx.BU_EXACTFIT )
		self.Bind( wx.EVT_BUTTON, self.onPrint, self.printButton )
		hs.Add( self.printButton, 0, border = border, flag = (flag & ~wx.LEFT) )
		
		self.grid = gridlib.Grid( self )
		self.colNameFields = [
			('Active',				'active'),
			('Name',				'name'),
			('Gender',				'gender'),
			('Numbers',				'catStr'),
			('Start Offset',		'startOffset'),
			('Race Laps',			'numLaps'),
			('Lapped Riders Continue',	'lappedRidersMustContinue'),
			('Distance',			'distance'),
			('Distance is By',		'distanceType'),
			('First Lap Distance',	'firstLapDistance'),
			('80% Lap Time',		'rule80Time'),
			('Suggested Laps',		'suggestedLaps'),
		]
		self.computedFieldss = {'rule80Time', 'suggestedLaps'}
		colnames = [colName for colName, fieldName in self.colNameFields]
		self.iCol = dict( (fieldName, i) for i, (colName, fieldName) in enumerate(self.colNameFields) )
		
		self.activeColumn = self.iCol['active']
		self.genderColumn = self.iCol['gender']
		self.grid.CreateGrid( 0, len(colnames) )
		self.grid.SetRowLabelSize(0)
		self.grid.SetMargins(0,0)
		for col, name in enumerate(colnames):
			self.grid.SetColLabelValue( col, name )
		self.cb = None

		#self.Bind( gridlib.EVT_GRID_CELL_LEFT_CLICK, self.onGridLeftClick )
		self.Bind( gridlib.EVT_GRID_SELECT_CELL, self.onCellSelected )
		self.Bind( gridlib.EVT_GRID_EDITOR_CREATED, self.onEditorCreated )
		
		vs.Add( hs, 0, flag=wx.EXPAND|wx.ALL, border = 4 )
		vs.Add( self.grid, 1, flag=wx.GROW|wx.ALL|wx.EXPAND )
		
		self.SetSizer(vs)

	def onPrint( self, event ):
		mainWin = Utils.getMainWin()
		if not mainWin:
			return
		race = Model.race
		if not Model.race:
			return
			
		colnames = ['Name', 'Gender', 'Numbers', 'Start Offset', 'Laps', 'Distance']
		data = [[]] * len(colnames)
		
		pdd = wx.PrintDialogData(mainWin.printData)
		pdd.SetAllPages( True )
		pdd.EnableSelection( False )
		pdd.EnablePageNumbers( False )
		pdd.EnableHelp( False )
		pdd.EnablePrintToFile( False )
		
		printer = wx.Printer(pdd)
		printout = CategoriesPrintout()

		if not printer.Print(self, printout, True):
			if printer.GetLastError() == wx.PRINTER_ERROR:
				Utils.MessageOK(self, "There was a printer problem.\nCheck your printer setup.", "Printer Error",iconMask=wx.ICON_ERROR)
		else:
			mainWin.printData = wx.PrintData( printer.GetPrintDialogData().GetPrintData() )

		printout.Destroy()
		
	def onGridLeftClick( self, event ):
		if event.GetCol() == self.activeColumn:
			wx.CallLater( 200, self.toggleCheckBox )
		event.Skip()
		
	def toggleCheckBox( self ):
		self.cb.SetValue( not self.cb.GetValue() )
		self.afterCheckBox( self.cb.GetValue() )
		
	def onCellSelected( self, event ):
		col = event.GetCol()
		if col == self.activeColumn or col == self.genderColumn:
			wx.CallAfter( self.grid.EnableCellEditControl )
		event.Skip()

	def onEditorCreated( self, event ):
		if event.GetCol() == self.activeColumn:
			self.cb = event.GetControl()
			self.cb.Bind( wx.EVT_CHECKBOX, self.onCheckBox )
		event.Skip()

	def onCheckBox( self, event ):
		self.afterCheckBox( event.IsChecked() )

	def afterCheckBox( self, isChecked ):
		pass
		
	def onAddExceptions( self, event ):
		with Model.LockRace() as race:
			if not race or not race.getAllCategories():
				return
				
		r = self.grid.GetGridCursorRow()
		if r is None or r < 0:
			Utils.MessageOK( self, 'You must select a Category first', 'Select a Category' )
			return
		
		with Model.LockRace() as race:
			categories = race.getAllCategories()
			category = categories[r]
			
		dlg = wx.TextEntryDialog( self,
									'\n'.join([
										'%s: Add Bib Exceptions (comma separated).',
										'',
										'This will add the given list of Bibs to this category,',
										'and remove them from other categories.']) % category.name,
									'Add Bib Exceptions' )
		good = (dlg.ShowModal() == wx.ID_OK)
		if good:
			response = dlg.GetValue()
		dlg.Destroy()
		if not good:
			return

		undo.pushState()
		response = re.sub( '[^0-9,]', '', response.replace(' ', ',') )
		with Model.LockRace() as race:
			for numException in response.split(','):
				race.addCategoryException( category, numException )

		self.refresh()
		
	def _setRow( self, r, active, name, catStr, startOffset = '00:00:00',
					numLaps = None,
					lappedRidersMustContinue = False,
					distance = None, distanceType = None,
					firstLapDistance = None, gender = None ):
		if len(startOffset) < len('00:00:00'):
			startOffset = '00:' + startOffset
	
		c = self.iCol['active']
		self.grid.SetCellValue( r, c, '1' if active else '0' )
		boolEditor = gridlib.GridCellBoolEditor()
		boolEditor.UseStringValues( '1', '0' )
		self.grid.SetCellEditor( r, c, boolEditor )
		self.grid.SetCellRenderer( r, c, gridlib.GridCellBoolRenderer() )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		
		self.grid.SetCellValue( r, self.iCol['name'], name )
		
		if not gender in {'Men', 'Women', 'Open'}:
			gender = 'Open'
		c = self.iCol['gender']
		self.grid.SetCellValue( r, c, gender )
		self.grid.SetCellEditor( r, c, gridlib.GridCellChoiceEditor(['Open','Men','Women'], False) )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_LEFT, wx.ALIGN_CENTRE )
		
		self.grid.SetCellValue( r, self.iCol['catStr'], catStr )
		
		c = self.iCol['startOffset']
		self.grid.SetCellValue( r, c, startOffset )
		self.grid.SetCellEditor( r, c, TimeEditor() )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		
		c = self.iCol['numLaps']
		self.grid.SetCellValue( r, c, str(numLaps) if numLaps else '' )
		numberEditor = wx.grid.GridCellNumberEditor()
		self.grid.SetCellEditor( r, c, numberEditor )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		
		c = self.iCol['lappedRidersMustContinue']
		self.grid.SetCellValue( r, c, '1' if lappedRidersMustContinue else '0' )
		boolEditor = gridlib.GridCellBoolEditor()
		boolEditor.UseStringValues( '1', '0' )
		self.grid.SetCellEditor( r, c, boolEditor )
		self.grid.SetCellRenderer( r, c, gridlib.GridCellBoolRenderer() )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		
		c = self.iCol['rule80Time']
		self.grid.SetCellValue( r, c, '' )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		self.grid.SetReadOnly( r, c, True )
		
		c = self.iCol['suggestedLaps']
		self.grid.SetCellValue( r, c, '' )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		self.grid.SetReadOnly( r, c, True )
		
		c = self.iCol['distance']
		self.grid.SetCellValue( r, c, ('%.3f' % distance) if distance else '' )
		self.grid.SetCellEditor( r, c, gridlib.GridCellFloatEditor(7, 3) )
		self.grid.SetCellRenderer( r, c, gridlib.GridCellFloatRenderer(7, 3) )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_RIGHT, wx.ALIGN_CENTRE )
		
		c = self.iCol['distanceType']
		choices = 'Lap,Race'
		self.grid.SetCellValue( r, c, '%d' % (distanceType if distanceType else 0) )
		self.grid.SetCellEditor( r, c, gridlib.GridCellEnumEditor(choices) )
		self.grid.SetCellRenderer( r, c, CustomEnumRenderer(choices) )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_RIGHT, wx.ALIGN_CENTRE )
		
		c = self.iCol['firstLapDistance']
		self.grid.SetCellValue( r, c, ('%.3f' % firstLapDistance) if firstLapDistance else '' )
		self.grid.SetCellEditor( r, c, gridlib.GridCellFloatEditor(7, 3) )
		self.grid.SetCellRenderer( r, c, gridlib.GridCellFloatRenderer(7, 3) )
		self.grid.SetCellAlignment( r, c, wx.ALIGN_RIGHT, wx.ALIGN_CENTRE )
		
		# Get the 80% time cutoff.
		if not active or not Model.race:
			return
			
		race = Model.race
		category = race.categories.get(name, None)
		if not category:
			return
			
		rule80Time = race.getRule80CountdownTime( category )
		if rule80Time:
			self.grid.SetCellValue( r, self.iCol['rule80Time'], Utils.formatTime(rule80Time) )
		
		laps = race.getCategoryRaceLaps().get(category, 0)
		if laps:
			self.grid.SetCellValue( r, self.iCol['suggestedLaps'], str(laps) )
		
	def onNewCategory( self, event ):
		self.grid.AppendRows( 1 )
		self._setRow( r=self.grid.GetNumberRows() - 1, active=True, name='<CategoryName>     ', catStr='100-199,504,-128' )
		self.grid.AutoSizeColumns(True)
		
	def onDelCategory( self, event ):
		r = self.grid.GetGridCursorRow()
		if r is None or r < 0:
			return
		if Utils.MessageOKCancel(self,	'Delete Category "%s"?' % self.grid.GetCellValue(r, 1).strip(),
										'Delete Category' ):
			self.grid.DeleteRows( r, 1, True )
		
	def onUpCategory( self, event ):
		r = self.grid.GetGridCursorRow()
		Utils.SwapGridRows( self.grid, r, r-1 )
		if r-1 >= 0:
			self.grid.MoveCursorUp( False )
		
	def onDownCategory( self, event ):
		r = self.grid.GetGridCursorRow()
		Utils.SwapGridRows( self.grid, r, r+1 )
		if r+1 < self.grid.GetNumberRows():
			self.grid.MoveCursorDown( False )
		
	def refresh( self ):
		with Model.LockRace() as race:
			self.grid.ClearGrid()
			if race is None:
				return
			
			for c in xrange(self.grid.GetNumberCols()):
				if self.grid.GetColLabelValue(c).startswith('Distance'):
					self.grid.SetColLabelValue( c, 'Distance (%s)' % ['km', 'miles'][getattr(race, 'distanceUnit', 0)] )
					break
			
			categories = race.getAllCategories()
			
			if self.grid.GetNumberRows() > 0:
				self.grid.DeleteRows( 0, self.grid.GetNumberRows() )
			self.grid.AppendRows( len(categories) )

			for r, cat in enumerate(categories):
				self._setRow(	r=r,
								active				= cat.active,
								name				= cat.name,
								gender				= getattr(cat, 'gender', None),
								catStr				= cat.catStr,
								startOffset			= cat.startOffset,
								numLaps				= cat.numLaps,
								lappedRidersMustContinue = getattr(cat, 'lappedRidersMustContinue', False),
								distance			= getattr(cat, 'distance', None),
								distanceType		= getattr(cat, 'distanceType', Model.Category.DistanceByLap),
								firstLapDistance	= getattr(cat, 'firstLapDistance', None),
							)
				
			self.grid.AutoSizeColumns( True )
			
			# Force the grid to the correct size.
			self.grid.FitInside()

	def commit( self ):
		undo.pushState()
		with Model.LockRace() as race:
			self.grid.DisableCellEditControl()	# Make sure the current edit is committed.
			if race is None:
				return
			numStrTuples = []
			for r in xrange(self.grid.GetNumberRows()):
				values = dict( (name, self.grid.GetCellValue(r, c)) for name, c in self.iCol.iteritems()
																			if name not in self.computedFieldss )
				numStrTuples.append( values )
			race.setCategories( numStrTuples )
	
if __name__ == '__main__':
	app = wx.PySimpleApp()
	mainWin = wx.Frame(None,title="CrossMan", size=(600,400))
	Model.setRace( Model.Race() )
	race = Model.getRace()
	race.setCategories( [
							{'name':'test1', 'catStr':'100-199,999','gender':'Men'},
							{'name':'test2', 'catStr':'200-299,888', 'startOffset':'00:10', 'distance':'6'},
							{'name':'test3', 'catStr':'300-399', 'startOffset':'00:20','gender':'Women'},
							{'name':'test4', 'catStr':'400-499', 'startOffset':'00:30','gender':'Open'},
							{'name':'test5', 'catStr':'500-599', 'startOffset':'01:00','gender':'Men'},
						] )
	categories = Categories(mainWin)
	categories.refresh()
	mainWin.Show()
	app.MainLoop()
