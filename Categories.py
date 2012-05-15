import wx
import re
import Model
import Utils
from Undo import undo
import wx.grid			as gridlib
import wx.lib.masked	as  masked

#--------------------------------------------------------------------------------
class TimeEditor(gridlib.PyGridCellEditor):
	def __init__(self):
		self._tc = None
		self.startValue = '00:00:00'
		gridlib.PyGridCellEditor.__init__(self)
		
	def Create( self, parent, id, evtHandler ):
		self._tc = masked.TimeCtrl( parent, id, style=wx.TE_CENTRE, fmt24hr=True, displaySeconds = False, value = '00:00:00' )
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

#--------------------------------------------------------------------------------
class Categories( wx.Panel ):
	def __init__( self, parent, id = wx.ID_ANY ):
		wx.Panel.__init__(self, parent, id)
		
		gbs = wx.GridBagSizer(4, 4)
		
		border = 6
		flag = wx.LEFT|wx.TOP|wx.BOTTOM
		
		cols = 0
		self.newCategoryButton = wx.Button(self, id=wx.ID_ANY, label='&New Category', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onNewCategory, self.newCategoryButton )
		gbs.Add( self.newCategoryButton, pos=(0,cols), span=(1,1), border = border, flag = flag )
		cols += 1 
		
		self.delCategoryButton = wx.Button(self, id=wx.ID_ANY, label='&Delete Category', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onDelCategory, self.delCategoryButton )
		gbs.Add( self.delCategoryButton, pos=(0,cols), span=(1,1), border = border, flag = flag )
		cols += 1 

		self.upCategoryButton = wx.Button(self, id=wx.ID_ANY, label='&Up', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onUpCategory, self.upCategoryButton )
		gbs.Add( self.upCategoryButton, pos=(0,cols), span=(1,1), border = border, flag = flag )
		cols += 1 

		self.downCategoryButton = wx.Button(self, id=wx.ID_ANY, label='D&own', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onDownCategory, self.downCategoryButton )
		gbs.Add( self.downCategoryButton, pos=(0,cols), span=(1,1), border = border, flag = (flag & ~wx.LEFT) )
		cols += 1 

		self.addExceptionsButton = wx.Button(self, id=wx.ID_ANY, label='&Add Bib Exceptions', style=wx.BU_EXACTFIT)
		self.Bind( wx.EVT_BUTTON, self.onAddExceptions, self.addExceptionsButton )
		gbs.Add( self.addExceptionsButton, pos=(0,cols), span=(1,1), border = border, flag = (flag & ~wx.LEFT) )
		cols += 1 

		self.grid = gridlib.Grid( self )
		colnames = ['Active', 'Name', 'Numbers', 'Start Offset (MM:SS)', 'Race Laps', '80% Lap Time', 'Suggested Laps']
		self.activeColumn = colnames.index( 'Active' )
		self.grid.CreateGrid( 0, len(colnames) )
		self.grid.SetRowLabelSize(0)
		self.grid.SetMargins(0,0)
		for col, name in enumerate(colnames):
			self.grid.SetColLabelValue( col, name )
		self.cb = None

		#self.Bind( gridlib.EVT_GRID_CELL_LEFT_CLICK, self.onGridLeftClick )
		self.Bind( gridlib.EVT_GRID_SELECT_CELL, self.onCellSelected )
		self.Bind( gridlib.EVT_GRID_EDITOR_CREATED, self.onEditorCreated )
		gbs.Add( self.grid, pos=(1,0), span=(1,cols), flag=wx.GROW|wx.ALL|wx.EXPAND )
		
		gbs.AddGrowableRow( 1 )
		gbs.AddGrowableCol( cols - 1 )
		self.SetSizer(gbs)

	def onGridLeftClick( self, event ):
		if event.GetCol() == self.activeColumn:
			wx.CallLater( 200, self.toggleCheckBox )
		event.Skip()
		
	def toggleCheckBox( self ):
		self.cb.SetValue( not self.cb.GetValue() )
		self.afterCheckBox( self.cb.GetValue() )
		
	def onCellSelected( self, event ):
		if event.GetCol() == self.activeColumn:
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
		r = self.grid.GetGridCursorRow()
		if r is None or r < 0:
			Utils.MessageOK( self, 'You must select a Category first', 'Select a Category' )
			return
			
		with Model.LockRace() as race:
			if not race:
				return
			categories = [c for c in race.categories.itervalues()]
			categories.sort()
		dlg = wx.TextEntryDialog( self,
									'%s: Add Bib Num Exceptions (comma separated)\nAdjust other categories as necessary.' % categories[r].name,
									'Add Bib Exceptions' )
		good = (dlg.ShowModal() == wx.ID_OK)
		if good:
			response = dlg.GetValue()
		dlg.Destroy()
		if not good:
			return

		response = re.sub( '[^0-9,]', '', response.replace(' ', ',') )
		for f in response.split(','):
			try:
				num = int(f)
				for i in xrange( len(categories) ):
					if i != r:
						categories[i].removeNum( num )
				categories[r].addNum( num )
			except ValueError:
				pass

		Model.race.setCategoryMask()
		self.refresh()
		
	def _setRow( self, r, active, name, strVal, startOffset, numLaps ):
		self.grid.SetCellValue( r, 0, '1' if active else '0' )
		boolEditor = gridlib.GridCellBoolEditor()
		boolEditor.UseStringValues( '1', '0' )
		self.grid.SetCellEditor( r, 0, boolEditor )
		self.grid.SetCellRenderer( r, 0, gridlib.GridCellBoolRenderer() )
		self.grid.SetCellAlignment( r, 0, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		self.grid.SetCellValue( r, 1, name )
		self.grid.SetCellValue( r, 2, strVal )
		self.grid.SetCellValue( r, 3, startOffset )
		self.grid.SetCellEditor( r, 3, TimeEditor() )
		self.grid.SetCellAlignment( r, 3, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		
		self.grid.SetCellValue( r, 4, str(numLaps) if numLaps else '' )
		numberEditor = wx.grid.GridCellNumberEditor()
		self.grid.SetCellEditor( r, 4, numberEditor )
		self.grid.SetCellAlignment( r, 4, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		
		self.grid.SetCellValue( r, 5, '' )
		self.grid.SetCellAlignment( r, 5, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		self.grid.SetReadOnly( r, 5, True )
		
		self.grid.SetCellValue( r, 6, '' )
		self.grid.SetCellAlignment( r, 6, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE )
		self.grid.SetReadOnly( r, 6, True )
		
		# Get the 80% time cutoff.
		if not active or not Model.race:
			return
			
		race = Model.race
		category = race.categories.get(name, None)
		if not category:
			return
			
		rule80Time = race.getRule80CountdownTime( category )
		if rule80Time:
			self.grid.SetCellValue( r, 5, Utils.formatTime(rule80Time) )
		
		laps = race.getCategoryRaceLaps().get(category, 0)
		if laps:
			self.grid.SetCellValue( r, 6, str(laps) )
		
	def onNewCategory( self, event ):
		self.grid.AppendRows( 1 )
		self._setRow( self.grid.GetNumberRows() - 1, True, '<CategoryName>     ', '100-199,504,-128', '00:00', None )
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
			
			categories = race.getAllCategories()
			
			if self.grid.GetNumberRows() > 0:
				self.grid.DeleteRows( 0, self.grid.GetNumberRows() )
			self.grid.AppendRows( len(categories) )

			for r, cat in enumerate(categories):
				self._setRow( r, cat.active, cat.name, cat.catStr, cat.startOffset, cat.numLaps )
				
			self.grid.AutoSizeColumns( True )
			
			# Force the grid to the correct size.
			self.grid.FitInside()

	def commit( self ):
		undo.pushState()
		with Model.LockRace() as race:
			self.grid.DisableCellEditControl()	# Make sure the current edit is committed.
			if race is None:
				return
			numStrTuples = [ tuple(self.grid.GetCellValue(r, c) for c in xrange(5)) for r in xrange(self.grid.GetNumberRows()) ]
			race.setCategories( numStrTuples )
	
if __name__ == '__main__':
	app = wx.PySimpleApp()
	mainWin = wx.Frame(None,title="CrossMan", size=(600,400))
	Model.setRace( Model.Race() )
	race = Model.getRace()
	race.setCategories( [(True, 'test1', '100-199,999', '00:00', 5),
						 (True, 'test2', '200-299,888', '00:00', '6'),
						 (True, 'test3', '300-399', '00:00', None),
						 (True, 'test4', '400-499', '00:00', None),
						 (True, 'test5', '500-599', '00:00', None),
						 ] )
	categories = Categories(mainWin)
	categories.refresh()
	mainWin.Show()
	app.MainLoop()
