import wx
from wx.lib.wordwrap import wordwrap
import sys
import os
import re
import datetime
import random
import time
import json
import webbrowser
import locale
import traceback
import xlwt
import wx.lib.agw.flatnotebook as fnb

FontSize = 24

locale.setlocale(locale.LC_ALL, '')
try:
	localDateFormat = locale.nl_langinfo( locale.D_FMT )
	localTimeFormat = locale.nl_langinfo( locale.T_FMT )
except:
	localDateFormat = '%b %d, %Y'
	localTimeFormat = '%I:%M%p'
	
import cPickle as pickle
from optparse import OptionParser

import SeriesModel
from Races				import Races
from Points				import Points
from Results			import Results
from Errors				import Errors
import Utils
import Model
import cStringIO as StringIO
import Version
from Printing			import SeriesMgrPrintout
from ExportGrid			import ExportGrid, tag
import cStringIO as StringIO

import wx.lib.agw.advancedsplash as AS
import openpyxl

#----------------------------------------------------------------------------------

def ShowSplashScreen():
	bitmap = wx.Bitmap( os.path.join(Utils.getImageFolder(), 'SeriesMgrSplash.png'), wx.BITMAP_TYPE_PNG )
	
	# Write in the version number into the bitmap.
	w, h = bitmap.GetSize()
	dc = wx.MemoryDC()
	dc.SelectObject( bitmap )
	dc.SetFont( wx.FontFromPixelSize( wx.Size(0,h//10), wx.FONTFAMILY_SWISS, wx.NORMAL, wx.FONTWEIGHT_NORMAL ) )
	dc.DrawText( Version.AppVerName.replace('SeriesMgr','Version'), w // 20, int(h * 0.4) )
	dc.SelectObject( wx.NullBitmap )
	
	# Show the splash screen.
	estyle = AS.AS_TIMEOUT | AS.AS_CENTER_ON_PARENT | AS.AS_SHADOW_BITMAP
	shadow = wx.Colour( 64, 64, 64 )
	showSeconds = 2.5
	try:
		frame = AS.AdvancedSplash(Utils.getMainWin(), bitmap=bitmap, timeout=int(showSeconds*1000),
								  extrastyle=estyle, shadowcolour=shadow)
	except:
		try:
			frame = AS.AdvancedSplash(Utils.getMainWin(), bitmap=bitmap, timeout=int(showSeconds*1000),
									  shadowcolour=shadow)
		except:
			pass

#----------------------------------------------------------------------------------
		
class MyTipProvider( wx.PyTipProvider ):
	def __init__( self, fname, tipNo = None ):
		self.tips = []
		try:
			with open(fname, 'r') as f:
				for line in f:
					line = line.strip()
					if line and line[0] != '#':
						self.tips.append( line )
			if tipNo is None:
				tipNo = (int(round(time.time() * 1000)) * 13) % (len(self.tips) - 1)
		except:
			pass
		if tipNo is None:
			tipNo = 0
		self.tipNo = tipNo
		wx.PyTipProvider.__init__( self, self.tipNo )
			
	def GetCurrentTip( self ):
		if self.tipNo < 0 or self.tipNo >= len(self.tips):
			self.tipNo = 0
		return self.tipNo
		
	def GetTip( self ):
		if not self.tips:
			return 'No tips available.'
		tip = self.tips[self.GetCurrentTip()].replace(r'\n','\n').replace(r'\t','    ')
		self.tipNo += 1
		return tip
		
	def PreprocessTip( self, tip ):
		return tip
		
	def DeleteFirstTip( self ):
		if self.tips:
			self.tips.pop(0)
		
	def __len__( self ):
		return len(self.tips)
		
	@property
	def CurrentTip( self ):
		return self.GetCurrentTip()
		
	@property
	def Tip( self ):
		return self.GetTip()

def ShowTipAtStartup():
	mainWin = Utils.getMainWin()
	if mainWin and not mainWin.config.ReadBool('showTipAtStartup', True):
		return
	
	tipFile = os.path.join(Utils.getImageFolder(), "tips.txt")
	try:
		provider = MyTipProvider( tipFile )
		'''
		if VersionMgr.isUpgradeRecommended():
			provider.tipNo = 0
		else:
			provider.DeleteFirstTip()
		'''
		showTipAtStartup = wx.ShowTip( None, provider, True )
		if mainWin:
			mainWin.config.WriteBool('showTipAtStartup', showTipAtStartup)
	except:
		pass

#----------------------------------------------------------------------------------
		
class MainWin( wx.Frame ):
	def __init__( self, parent, id = wx.ID_ANY, title='', size=(200,200) ):
		wx.Frame.__init__(self, parent, id, title, size=size)

		Utils.setMainWin( self )

		# Add code to configure file history.
		self.filehistory = wx.FileHistory(8)
		self.config = wx.Config(appName="SeriesMgr",
								vendorName="SmartCyclingSolutions",
								style=wx.CONFIG_USE_LOCAL_FILE)
		self.filehistory.Load(self.config)
		
		self.fileName = None
		
		# Setup the objects for the race clock.
		self.timer = wx.Timer( self, id=wx.NewId() )
		self.secondCount = 0

		# Default print options.
		self.printData = wx.PrintData()
		self.printData.SetPaperId(wx.PAPER_LETTER)
		self.printData.SetPrintMode(wx.PRINT_MODE_PRINTER)
		#self.printData.SetOrientation(wx.PORTRAIT)

		# Configure the main menu.
		self.menuBar = wx.MenuBar(wx.MB_DOCKABLE)

		#-----------------------------------------------------------------------
		self.fileMenu = wx.Menu()

		self.fileMenu.Append( wx.ID_NEW , "&New...", "Create a new Series" )
		self.Bind(wx.EVT_MENU, self.menuNew, id=wx.ID_NEW )

		self.fileMenu.Append( wx.ID_OPEN , "&Open...", "Open an existing Series" )
		self.Bind(wx.EVT_MENU, self.menuOpen, id=wx.ID_OPEN )

		self.fileMenu.Append( wx.ID_SAVE , "&Save\tCtrl+S", "Save Series" )
		self.Bind(wx.EVT_MENU, self.menuSave, id=wx.ID_SAVE )

		self.fileMenu.Append( wx.ID_SAVEAS , "Save &As...", "Save to a different filename" )
		self.Bind(wx.EVT_MENU, self.menuSaveAs, id=wx.ID_SAVEAS )

		self.fileMenu.AppendSeparator()
		self.fileMenu.Append( wx.ID_PAGE_SETUP , "Page &Setup...", "Setup the print page" )
		self.Bind(wx.EVT_MENU, self.menuPageSetup, id=wx.ID_PAGE_SETUP )

		self.fileMenu.Append( wx.ID_PREVIEW , "Print P&review...\tCtrl+R", "Preview Results" )
		self.Bind(wx.EVT_MENU, self.menuPrintPreview, id=wx.ID_PREVIEW )

		self.fileMenu.Append( wx.ID_PRINT , "&Print...\tCtrl+P", "Print Results" )
		self.Bind(wx.EVT_MENU, self.menuPrint, id=wx.ID_PRINT )

		self.fileMenu.AppendSeparator()

		'''
		idCur = wx.NewId()
		self.fileMenu.Append( idCur , "&Export to Excel...", "Export to an Excel Spreadsheet (.xls)" )
		self.Bind(wx.EVT_MENU, self.menuExportToExcel, id=idCur )
		
		idCur = wx.NewId()
		self.fileMenu.Append( idCur , "Export to &HTML...", "Export to HTML (.html)" )
		self.Bind(wx.EVT_MENU, self.menuExportToHtml, id=idCur )

		self.fileMenu.AppendSeparator()
		'''
		
		recent = wx.Menu()
		self.fileMenu.AppendMenu(wx.ID_ANY, "&Recent Files", recent)
		self.filehistory.UseMenu( recent )
		self.filehistory.AddFilesToMenu()
		
		self.fileMenu.AppendSeparator()

		self.fileMenu.Append( wx.ID_EXIT, "E&xit", "Exit" )
		self.Bind(wx.EVT_MENU, self.menuExit, id=wx.ID_EXIT )
		
		self.Bind(wx.EVT_MENU_RANGE, self.menuFileHistory, id=wx.ID_FILE1, id2=wx.ID_FILE9)
		
		self.menuBar.Append( self.fileMenu, "&File" )

		#-----------------------------------------------------------------------

		# Configure the field of the display.

		sty = wx.BORDER_SUNKEN
		self.notebook = fnb.FlatNotebook(self, wx.ID_ANY, agwStyle=fnb.FNB_VC8|fnb.FNB_NO_X_BUTTON)
		font = wx.FontFromPixelSize( wx.Size(0,(FontSize*4)//5), wx.FONTFAMILY_SWISS, wx.NORMAL, wx.FONTWEIGHT_NORMAL )
		self.notebook.SetFont( font )
		self.notebook.Bind( fnb.EVT_FLATNOTEBOOK_PAGE_CHANGED, self.onPageChanging )
		
		# Add all the pages to the notebook.
		self.pages = []

		def addPage( page, name ):
			self.notebook.AddPage( page, name )
			self.pages.append( page )
			
		self.attrClassName = [
			[ 'races',			Races,				'Races' ],
			[ 'points',			Points,				'Points' ],
			[ 'results',		Results,			'Results' ],
			[ 'errors',			Errors,				'Errors' ],
		]
		
		for i, (a, c, n) in enumerate(self.attrClassName):
			setattr( self, a, c(self.notebook) )
			addPage( getattr(self, a), n )
			
		self.notebook.SetSelection( 0 )
		
		#-----------------------------------------------------------------------
		self.helpMenu = wx.Menu()

		idCur = wx.NewId()
		self.helpMenu.Append( wx.ID_HELP , "&Help...", "Help about SeriesMgr..." )
		self.Bind(wx.EVT_MENU, self.menuHelp, id=wx.ID_HELP )
		
		self.helpMenu.AppendSeparator()

		self.helpMenu.Append( wx.ID_ABOUT , "&About...", "About SeriesMgr..." )
		self.Bind(wx.EVT_MENU, self.menuAbout, id=wx.ID_ABOUT )

		idCur = wx.NewId()
		self.helpMenu.Append( idCur , "&Tips at Startup...", "Enable/Disable Tips at Startup..." )
		self.Bind(wx.EVT_MENU, self.menuTipAtStartup, id=idCur )

		self.menuBar.Append( self.helpMenu, "&Help" )

		#------------------------------------------------------------------------------
		self.SetMenuBar( self.menuBar )
		
		#------------------------------------------------------------------------------
		self.Bind(wx.EVT_CLOSE, self.onCloseWindow)
		
		sizer = wx.BoxSizer( wx.VERTICAL )
		sizer.Add( self.notebook, 1, flag=wx.EXPAND )
		self.SetSizer( sizer )
		
		wx.CallAfter( self.Refresh )

	def resetEvents( self ):
		self.events.reset()
		
	def menuUndo( self, event ):
		undo.doUndo()
		self.refresh()
		
	def menuRedo( self, event ):
		undo.doRedo()
		self.refresh()
		
	def menuTipAtStartup( self, event ):
		showing = self.config.ReadBool('showTipAtStartup', True)
		if Utils.MessageOKCancel( self, 'Turn Off Tips at Startup?' if showing else 'Show Tips at Startup?', 'Tips at Startup' ):
			self.config.WriteBool( 'showTipAtStartup', showing ^ True )

	def menuChangeProperties( self, event ):
		if not SeriesModel.model:
			Utils.MessageOK(self, "You must have a valid Series.", "No Valid Race", iconMask=wx.ICON_ERROR)
			return
		ChangeProperties( self )
				
	def getDirName( self ):
		return Utils.getDirName()
		
	def menuPageSetup( self, event ):
		psdd = wx.PageSetupDialogData(self.printData)
		psdd.CalculatePaperSizeFromId()
		dlg = wx.PageSetupDialog(self, psdd)
		dlg.ShowModal()

		# this makes a copy of the wx.PrintData instead of just saving
		# a reference to the one inside the PrintDialogData that will
		# be destroyed when the dialog is destroyed
		self.printData = wx.PrintData( dlg.GetPageSetupData().GetPrintData() )
		dlg.Destroy()

	def getTitle( self ):
		model = SeriesModel.model
		iSelection = self.notebook.GetSelection()
		try:
			pageTitle = self.pages[iSelection].getTitle()
		except:
			pageTitle = self.attrClassName[iSelection][2]
			
		title = '%s\n%s' % (
			pageTitle, model.name
		)
		return title
	
	def menuPrintPreview( self, event ):
		self.commit()
		title = self.getTitle()
		page = self.pages[self.notebook.GetSelection()]
		try:
			grid = page.getGrid()
			printout = SeriesMgrPrintout( title, grid )
			printout2 = SeriesMgrPrintout( title, grid )
		except AttributeError:
			return
		
		data = wx.PrintDialogData(self.printData)
		self.preview = wx.PrintPreview(printout, printout2, data)

		self.preview.SetZoom( 110 )
		if not self.preview.Ok():
			return

		pfrm = wx.PreviewFrame(self.preview, self, "Print preview")

		pfrm.Initialize()
		pfrm.SetPosition(self.GetPosition())
		pfrm.SetSize(self.GetSize())
		pfrm.Show(True)

	def menuPrint( self, event ):
		self.commit()
		title = self.getTitle()
		page = self.pages[self.notebook.GetSelection()]
		try:
			grid = page.getGrid()
			printout = SeriesMgrPrintout( title, grid )
		except AttributeError:
			if page == self.graphDraw:
				printout = GraphDrawPrintout( title, page )
			else:
				return
		
		pdd = wx.PrintDialogData(self.printData)
		pdd.SetAllPages( 1 )
		pdd.EnablePageNumbers( 0 )
		pdd.EnableHelp( 0 )
		
		printer = wx.Printer(pdd)

		if not printer.Print(self, printout, True):
			if printer.GetLastError() == wx.PRINTER_ERROR:
				Utils.MessageOK(self, "There was a printer problem.\nCheck your printer setup.", "Printer Error",iconMask=wx.ICON_ERROR)
		else:
			self.printData = wx.PrintData( printer.GetPrintDialogData().GetPrintData() )

		printout.Destroy()

	#--------------------------------------------------------------------------------------------

	def menuExportToExcel( self, event ):
		self.commit()
		iSelection = self.notebook.GetSelection()
		page = self.pages[iSelection]
		try:
			grid = page.getGrid()
		except:
			return
		
		try:
			pageTitle = self.pages[iSelection].getTitle()
		except:
			pageTitle = self.attrClassName[iSelection][2]
		
		if not self.fileName or len(self.fileName) < 4:
			Utils.MessageOK(self, 'You must Save before you can Export to Excel', 'Excel Write')
			return

		pageTitle = Utils.RemoveDisallowedFilenameChars( pageTitle.replace('/', '_') )
		xlFName = self.fileName[:-4] + '-' + pageTitle + '.xls'
		dlg = wx.DirDialog( self, 'Folder to write "%s"' % os.path.basename(xlFName),
						style=wx.DD_DEFAULT_STYLE, defaultPath=os.path.dirname(xlFName) )
		ret = dlg.ShowModal()
		dName = dlg.GetPath()
		dlg.Destroy()
		if ret != wx.ID_OK:
			return

		xlFName = os.path.join( dName, os.path.basename(xlFName) )

		title = self.getTitle()
		
		wb = xlwt.Workbook()
		sheetName = self.attrClassName[self.notebook.GetSelection()][2]
		sheetCur = wb.add_sheet( sheetName )
		export = ExportGrid( title, grid )
		export.toExcelSheet( sheetCur )

		try:
			wb.save( xlFName )
			webbrowser.open( xlFName, new = 2, autoraise = True )
			Utils.MessageOK(self, 'Excel file written to:\n\n   %s' % xlFName, 'Excel Export')
		except IOError:
			Utils.MessageOK(self,
						'Cannot write "%s".\n\nCheck if this spreadsheet is open.\nIf so, close it, and try again.' % xlFName,
						'Excel File Error', iconMask=wx.ICON_ERROR )
						
	def menuExportToHtml( self, event ):
		self.commit()
		iSelection = self.notebook.GetSelection()
		page = self.pages[iSelection]
		try:
			grid = page.getGrid()
		except:
			return
		
		try:
			pageTitle = self.pages[iSelection].getTitle()
		except:
			pageTitle = self.attrClassName[iSelection][2]
		
		if not self.fileName or len(self.fileName) < 4:
			Utils.MessageOK(self, 'You must Save before you can Export to Html', 'Excel Export')
			return

		pageTitle = Utils.RemoveDisallowedFilenameChars( pageTitle.replace('/', '_') )
		htmlFName = self.fileName[:-4] + '-' + pageTitle + '.html'
		dlg = wx.DirDialog( self, 'Folder to write "%s"' % os.path.basename(htmlFName),
						style=wx.DD_DEFAULT_STYLE, defaultPath=os.path.dirname(htmlFName) )
		ret = dlg.ShowModal()
		dName = dlg.GetPath()
		dlg.Destroy()
		if ret != wx.ID_OK:
			return

		htmlFName = os.path.join( dName, os.path.basename(htmlFName) )

		title = self.getTitle()
		
		html = StringIO.StringIO()
		
		with tag(html, 'html'):
			with tag(html, 'head'):
				with tag(html, 'title'):
					html.write( title.replace('\n', ' ') )
				with tag(html, 'meta', dict(charset="UTF-8", author="Edward Sitarski", copyright="Edward Sitarski, 2013", generator="SeriesMgr")):
					pass
				with tag(html, 'style', dict( type="text/css")):
					html.write( '''
body{ font-family: sans-serif; }

#idRaceName {
	font-size: 200%;
	font-weight: bold;
}
#idImgHeader { box-shadow: 4px 4px 4px #888888; }
.smallfont { font-size: 80%; }
.bigfont { font-size: 120%; }
.hidden { display: none; }

table.results
{
	font-family:"Trebuchet MS", Arial, Helvetica, sans-serif;
	border-collapse:collapse;
}
table.results td, table.results th 
{
	font-size:1em;
	padding:3px 7px 2px 7px;
	text-align: left;
}
table.results th 
{
	font-size:1.1em;
	text-align:left;
	padding-top:5px;
	padding-bottom:4px;
	background-color:#7FE57F;
	color:#000000;
}
table.results tr.odd
{
	color:#000000;
	background-color:#EAF2D3;
}
table.results tr:hover
{
	color:#000000;
	background-color:#FFFFCC;
}
table.results tr.odd:hover
{
	color:#000000;
	background-color:#FFFFCC;
}

table.results td {
	border-top:1px solid #98bf21;
}

table.results td.noborder {
	border-top:0px solid #98bf21;
}

table.results td.rAlign, table.results th.rAlign {
	text-align:right;
}

table.results tr td.fastest{
	color:#000000;
	background-color:#80FF80;
}

@media print { .noprint { display: none; } }''' )

			with tag(html, 'body'):
				ExportGrid( title, grid ).toHtml(html)
		
		html = html.getvalue()
		
		try:
			with open(htmlFName, 'wb') as fp:
				fp.write( html )
			webbrowser.open( htmlFName, new = 2, autoraise = True )
			Utils.MessageOK(self, 'Html file written to:\n\n   %s' % htmlFName, 'Html Write')
		except IOError:
			Utils.MessageOK(self,
						'Cannot write "%s".\n\nCheck if this spreadsheet is open.\nIf so, close it, and try again.' % htmlFName,
						'Html File Error', iconMask=wx.ICON_ERROR )
	
	#--------------------------------------------------------------------------------------------
	def onCloseWindow( self, event ):
		self.showPageName( 'Results' )
		self.writeSeries()
		wx.Exit()

	def writeSeries( self ):
		self.commit()
		if not self.fileName:
			self.setTitle()
			return
		model = SeriesModel.model
		with open(self.fileName, 'wb') as fp:
			pickle.dump( model, fp, 2 )
		model.setChanged( False )
		self.setTitle()

	def menuNew( self, event ):
		self.showPageName( 'Results' )
		model = SeriesModel.model
		if model.changed:
			ret = Utils.MessageOKCancel( self, 'Save Existing Series?', 'Save Existing Series?' ) 
			if ret == wx.ID_CANCEL:
				return
			if ret == wx.ID_OK:
				self.writeSeries()
				
		SeriesModel.model = SeriesModel.SeriesModel()
		self.fileName = ''
		self.showPageName( 'Races' )
		self.refresh()
	
	def updateRecentFiles( self ):
		self.filehistory.AddFileToHistory(self.fileName)
		self.filehistory.Save(self.config)
		self.config.Flush()
		
	def openSeries( self, fileName ):
		if not fileName:
			return
		try:
			with open(fileName, 'rb') as fp:
				SeriesModel.model = pickle.load( fp )
		except IOError:
			Utils.MessageOK(self, 'Cannot Open File "%s".' % fileName, 'Cannot Open File', iconMask=wx.ICON_ERROR )
			return
		
		self.fileName = fileName
		self.updateRecentFiles()
		SeriesModel.model.setChanged( False )
		self.refreshAll()
		self.showPageName( 'Properties' )

	def menuOpen( self, event ):
		if SeriesModel.model.changed:
			if Utils.MessageOKCancel(self, 'You have Unsaved Changes.  Save Now?', 'Unsaved Changes') == wx.ID_OK:
				self.writeSeries()
			else:
				return
				
		dlg = wx.FileDialog( self, message="Choose a file for your Competition",
							defaultFile = '',
							wildcard = 'SeriesMgr files (*.smn)|*.smn',
							style=wx.OPEN | wx.CHANGE_DIR )
		if dlg.ShowModal() == wx.ID_OK:
			self.openSeries( dlg.GetPath() )
		dlg.Destroy()

	def menuSave( self, event ):
		if not self.fileName:
			self.menuSaveAs( event )
			return
		
		try:
			self.writeSeries()
		except:
			Utils.MessageOK(self, 'Write Failed.  Competition NOT saved."%s".' % fileName, 'Write Failed', iconMask=wx.ICON_ERROR )
		self.updateRecentFiles()

	def setTitle( self ):
		if self.fileName:
			title = '%s%s - %s' % ('*' if SeriesModel.model.changed else '', self.fileName, Version.AppVerName)
		else:
			title = Version.AppVerName
		self.SetTitle( title )
			
	def menuSaveAs( self, event ):
		dlg = wx.FileDialog( self, message="Choose a file for your Series",
							defaultFile = '',
							wildcard = 'SeriesMgr files (*.smn)|*.smn',
							style=wx.OPEN | wx.CHANGE_DIR )
		response = dlg.ShowModal()
		if response == wx.ID_OK:
			fileName = dlg.GetPath()
		dlg.Destroy()
		if response != wx.ID_OK:
			return
		
		try:
			with open(fileName, 'rb') as fp:
				pass
			if not Utils.MessageOKCancel(self, 'File Exists.  Replace?', 'File Exists'):
				return
		except IOError:
			pass
		
		try:
			with open(fileName, 'wb') as fp:
				pass
		except:
			Utils.MessageOK(self, 'Cannot open file "%s".' % fileName, 'Cannot Open File', iconMask=wx.ICON_ERROR )
			return
			
		self.fileName = fileName
		self.menuSave( event )
		
	def menuFileHistory( self, event ):
		fileNum = event.GetId() - wx.ID_FILE1
		fileName = self.filehistory.GetHistoryFile(fileNum)
		self.filehistory.AddFileToHistory(fileName)  # move up the list
		self.openSeries( fileName )
		
	def menuExit(self, event):
		if SeriesModel.model.changed:
			response = Utils.MessageYesNoCancel(self, 'You have Unsaved Changes.\nSave Before Closing?', 'Unsaved Changes')
			if response == wx.ID_CANCEL:
				return
			if response == wx.ID_OK:
				self.writeSeries()
				
		self.onCloseWindow( event )

	def menuHelpQuickStart( self, event ):
		Utils.showHelp( 'QuickStart.html' )
	
	def menuHelp( self, event ):
		Utils.showHelp( 'Main.html' )
	
	def onContextHelp( self, event ):
		Utils.showHelp( self.attrClassName[self.notebook.GetSelection()][2] + '.html' )
	
	def menuAbout( self, event ):
		# First we create and fill the info object
		info = wx.AboutDialogInfo()
		info.Name = Version.AppVerName
		info.Version = ''
		info.Copyright = "(C) 2013"
		info.Description = wordwrap(
			"Combine CrossMgr results into a Series.\n\n"
			"",
			500, wx.ClientDC(self))
		info.WebSite = ("http://sites.google.com/site/crossmgrsoftware/", "CrossMgr Home Page")
		info.Developers = [
					"Edward Sitarski (edward.sitarski@gmail.com)"
					]

		licenseText = "User Beware!\n\n" \
			"This program is experimental, under development and may have bugs.\n" \
			"Feedback is sincerely appreciated.\n\n" \
			"Donations are also appreciated - see website for details.\n\n" \
			"CRITICALLY IMPORTANT MESSAGE!\n" \
			"This program is not warrented for any use whatsoever.\n" \
			"It may not produce correct results, it might lose your data.\n" \
			"The authors of this program assume no reponsibility or liability for data loss or erronious results produced by this program.\n\n" \
			"Use entirely at your own risk.\n" \
			"Do not come back and tell me that this program screwed up your event!\n" \
			"Computers fail, screw-ups happen.  Always use a paper manual backup."
		info.License = wordwrap(licenseText, 500, wx.ClientDC(self))

		wx.AboutBox(info)

	#--------------------------------------------------------------------------------------

	def getCurrentPage( self ):
		return self.pages[self.notebook.GetSelection()]
	
	def showPage( self, iPage ):
		self.callPageCommit( self.notebook.GetSelection() )
		self.callPageRefresh( iPage )
		#self.notebook.ChangeSelection( iPage )
		self.notebook.SetSelection( iPage )
		self.pages[self.notebook.GetSelection()].Layout()
		self.Layout()

	def showPageName( self, name ):
		name = name.replace(' ', '')
		for i, (a, c, n) in enumerate(self.attrClassName):
			if n == name:
				self.showPage( i )
				break

	def commit( self ):
		self.callPageCommit( self.notebook.GetSelection() )
		self.setTitle()
				
	def refreshCurrentPage( self ):
		self.setTitle()
		self.callPageRefresh( self.notebook.GetSelection() )

	def refresh( self ):
		self.refreshCurrentPage()

	def callPageRefresh( self, i ):
		try:
			self.pages[i].refresh()
		except (AttributeError, IndexError) as e:
			pass

	def callPageCommit( self, i ):
		try:
			self.pages[i].commit()
			self.setTitle()
		except (AttributeError, IndexError) as e:
			pass

	def onPageChanging( self, event ):
		self.callPageCommit( event.GetOldSelection() )
		self.callPageRefresh( event.GetSelection() )
		event.Skip()	# Required to properly repaint the screen.

	def refreshAll( self ):
		self.refresh()
		iSelect = self.notebook.GetSelection()
		for i, p in enumerate(self.pages):
			if i != iSelect:
				self.callPageRefresh( i )
		self.setTitle()

# Set log file location.
dataDir = ''
redirectFileName = ''
			
def MainLoop():
	global dataDir
	global redirectFileName
	
	random.seed()

	app = wx.PySimpleApp()
	app.SetAppName("SeriesMgr")
	
	parser = OptionParser( usage = "usage: %prog [options] [RaceFile.smn]" )
	parser.add_option("-f", "--file", dest="filename", help="race file", metavar="RaceFile.smn")
	parser.add_option("-q", "--quiet", action="store_false", dest="verbose", default=True, help='hide splash screen')
	parser.add_option("-r", "--regular", action="store_false", dest="fullScreen", default=True, help='regular size (not full screen)')
	(options, args) = parser.parse_args()

	dataDir = Utils.getHomeDir()
	redirectFileName = os.path.join(dataDir, 'SeriesMgr.log')
	
	if __name__ == '__main__':
		Utils.disable_stdout_buffering()
			
	# Configure the main window.
	sWidth, sHeight = wx.GetDisplaySize()
	mainWin = MainWin( None, title=Version.AppVerName, size=(sWidth*0.9,sHeight*0.9) )
	if options.fullScreen:
		mainWin.Maximize( True )
		
	mainWin.refreshAll()
	mainWin.CenterOnScreen()
	mainWin.Show()

	# Set the upper left icon.
	icon = wx.Icon( os.path.join(Utils.getImageFolder(), 'SeriesMgr.ico'), wx.BITMAP_TYPE_ICO )
	#mainWin.SetIcon( icon )

	# Set the taskbar icon.
	#tbicon = wx.TaskBarIcon()
	#tbicon.SetIcon( icon, "SeriesMgr" )

	if options.verbose:
		ShowSplashScreen()
	#	ShowTipAtStartup()
	
	# Try to open a specified filename.
	fileName = options.filename
	
	# If nothing, try a positional argument.
	if not fileName and args:
		fileName = args[0]
	
	# Try to load a race.
	if fileName:
		try:
			mainWin.openSeries( fileName )
		except (IndexError, AttributeError, ValueError):
			pass

	# Start processing events.
	mainWin.GetSizer().Layout()
	try:
		app.MainLoop()
	except:
		xc = traceback.format_exception(*sys.exc_info())
		wx.MessageBox(''.join(xc))

if __name__ == '__main__':
	MainLoop()