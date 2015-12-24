import requests
import datetime
import os
import wx
import wx.gizmos as gizmos
import Utils
import Clock
import Model
from ReadSignOnSheet	import ExcelLink

def RaceDBUrlDefault():
	return 'http://{}:8000/RaceDB'.format( Utils.GetDefaultHost() )
	
def CrossMgrFolderDefault():
	return os.path.join( os.path.expanduser('~'), 'CrossMgrRaces' )

def GetRaceDBEvents( url = None, date=None ):
	url = url or RaceDBUrlDefault()
	url += '/GetEvents'
	if date:
		url += date.strftime('/%Y-%m-%d')
	req = requests.get( url + '/' )
	events = req.json()
	return events
	
def GetEventCrossMgr( url, eventId, eventType ):
	url = url or RaceDBUrlDefault()
	url +=['/EventMassStartCrossMgr','/EventTTCrossMgr'][eventType] + '/{}'.format(eventId)
	req = requests.get( url + '/' )
	content_disposition = req.headers['content-disposition'].encode('latin-1').decode('utf-8')
	filename = content_disposition.split('=')[1].replace("'",'').replace('"','')
	return filename, req.content

class RaceDB( wx.Dialog ):
	def __init__( self, parent, id=wx.ID_ANY, size=(600,700) ):
		super(RaceDB, self).__init__(parent, id, style=wx.DEFAULT_DIALOG_STYLE|wx.THICK_FRAME, size=size, title=_('Open RaceDB Event'))
		
		raceDBLogo = wx.StaticBitmap( self, bitmap=wx.Bitmap( os.path.join(Utils.getImageFolder(), 'RaceDB_big.png'), wx.BITMAP_TYPE_PNG ) )
		
		self.clock = Clock.Clock( self, size=(190,190) )
		
		self.raceFolder = wx.DirPickerCtrl( self, path=CrossMgrFolderDefault() )
		self.raceDBUrl = wx.TextCtrl( self, value=RaceDBUrlDefault(), style=wx.TE_PROCESS_ENTER )
		self.raceDBUrl.Bind( wx.EVT_TEXT_ENTER, self.onChange )
		self.datePicker = wx.DatePickerCtrl( self, size=(120,-1), style = wx.DP_DROPDOWN | wx.DP_SHOWCENTURY )
		self.datePicker.Bind( wx.EVT_DATE_CHANGED, self.onChange )
		
		fgs = wx.FlexGridSizer( cols=2, rows=0, vgap=4, hgap=4 )
		fgs.AddGrowableCol( 1, 1 )
		
		fgs.Add( wx.StaticText(self, label=_('Race Folder')), flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL )
		fgs.Add( self.raceFolder, 1, flag=wx.EXPAND )
		fgs.Add( wx.StaticText(self, label=_('RaceDB URL')), flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL )
		fgs.Add( self.raceDBUrl, 1, flag=wx.EXPAND )
		fgs.Add( wx.StaticText(self, label=_('All Events On')), flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL )
		
		hs = wx.BoxSizer( wx.HORIZONTAL )
		hs.Add( self.datePicker, flag=wx.ALIGN_CENTER_VERTICAL )
		self.updateButton = wx.Button( self, label=_('Update') )
		self.updateButton.Bind( wx.EVT_BUTTON, self.onChange )
		hs.Add( self.updateButton, flag=wx.LEFT, border=16 )
		fgs.Add( hs )
		
		hsHeader = wx.BoxSizer( wx.HORIZONTAL )
		hsHeader.Add( raceDBLogo )
		hsHeader.AddStretchSpacer()
		hsHeader.Add( self.clock, flag=wx.TOP|wx.RIGHT, border=8 )
		
		vsHeader = wx.BoxSizer( wx.VERTICAL )
		vsHeader.Add( hsHeader, flag=wx.EXPAND )
		vsHeader.Add( fgs, 1, flag=wx.EXPAND )
		
		self.tree = gizmos.TreeListCtrl( self, style=wx.TR_DEFAULT_STYLE|wx.TR_FULL_ROW_HIGHLIGHT|wx.TR_ROW_LINES )
		
		isz = (16,16)
		self.il = wx.ImageList( *isz )
		self.closedIdx		= self.il.Add( wx.ArtProvider_GetBitmap(wx.ART_FOLDER,	 	wx.ART_OTHER, isz))
		self.expandedIdx	= self.il.Add( wx.ArtProvider_GetBitmap(wx.ART_FILE_OPEN, 	wx.ART_OTHER, isz))
		self.fileIdx		= self.il.Add( wx.ArtProvider_GetBitmap(wx.ART_NORMAL_FILE,	wx.ART_OTHER, isz))
		self.selectedIdx	= self.il.Add( wx.ArtProvider_GetBitmap(wx.ART_LIST_VIEW, 	wx.ART_OTHER, isz))
		
		self.tree.SetImageList( self.il )
		
		self.tree.AddColumn( _('Event Info') )
		self.tree.AddColumn( _('Event Type'), flag=wx.ALIGN_LEFT )
		self.eventTypeCol = 1
		self.tree.AddColumn( _('Start Time'), flag=wx.ALIGN_RIGHT )
		self.startTimeCol = 2
		self.tree.AddColumn( _('Participants'), flag=wx.ALIGN_RIGHT)
		self.participantCountCol = 3
		
		self.tree.SetMainColumn( 0 )
		self.tree.SetColumnWidth( 0, 320 )
		self.tree.SetColumnWidth( self.eventTypeCol, 80 )
		self.tree.SetColumnWidth( self.startTimeCol, 80 )
		self.tree.SetColumnWidth( self.participantCountCol, 80 )
		
		self.tree.Bind( wx.EVT_TREE_SEL_CHANGED, self.selectChangedCB )
		self.dataSelect = None
		
		hs = wx.BoxSizer( wx.HORIZONTAL )
		self.okButton = wx.Button( self, label=_("Open Event") )
		self.okButton.Bind( wx.EVT_BUTTON, self.doOK )
		self.cancelButton = wx.Button( self, id=wx.ID_CANCEL )
		hs.Add( self.okButton )
		hs.AddStretchSpacer()
		hs.Add( self.cancelButton, flag=wx.LEFT, border=4 )
		
		vs = wx.BoxSizer( wx.VERTICAL )
		vs.Add( vsHeader, flag=wx.ALL|wx.EXPAND, border=8 )
		vs.Add( self.tree, 1, flag=wx.EXPAND )
		vs.Add( hs, 0, flag=wx.EXPAND|wx.ALL, border=8 )
		self.SetSizer( vs )
		
		self.refresh()

	def onChange( self, event ):
		wx.CallAfter( self.refresh )
	
	def fixUrl( self ):
		url = self.raceDBUrl.GetValue().strip()
		if not url:
			url = RaceDBUrlDefault()
		url = url.split('RaceDB')[0] + 'RaceDB'
		while url.endswith( '/' ):
			url = url[:-1]
		self.raceDBUrl.SetValue( url )
		return url
	
	def doOK( self, event ):
		url = self.fixUrl()
		
		try:
			filename, content = GetEventCrossMgr( url, self.dataSelect['pk'], self.dataSelect['event_type'] )
		except Exception as e:
			Utils.MessageOK(
				self,
				u'{}\n\n"{}"\n\n{}'.format(_('Error Connecting to RaceDB Server'), url, e),
				_('Error Connecting to RaceDB Server'),
				iconMask=wx.ICON_ERROR )
			return
		
		if not Utils.MessageOKCancel( self, u'{}:\n\n"{}"'.format( _('Confirm Open Event'), filename), _('Confirm Open Event') ):
			return
		
		dir = os.path.join(
			self.raceFolder.GetPath().strip() or CrossMgrFolderDefault(),
			Utils.RemoveDisallowedFilenameChars(self.dataSelect['competition_name']),
		)
		if not os.path.isdir(dir):
			try:
				os.makedirs( dir )
			except Exception as e:
				Utils.MessageOK(
					self,
					u'{}\n\n"{}"'.format( _('Error Creating Folder'), e),
					_('Error Creating Folder'),
					iconMask=wx.ICON_ERROR,
				)
				return
		
		excelFName = os.path.join(dir, filename)
		try:
			with open( excelFName, 'wb' ) as f:
				f.write( content )
		except Exception as e:
			Utils.MessageOKCancel(
				self,
				u'{}\n\n{}\n\n{}'.format( _('Error Writing File'), e, excelFName),
				_('Error Writing File'),
				iconMask=wx.ICON_ERROR,
			)
			return
		
		mainWin = Utils.getMainWin()
		if mainWin:
			mainWin.openRaceDBExcel( excelFName, overwriteExisting=False )
		self.EndModal( wx.ID_OK )
	
	def selectChangedCB( self, evt ):
		try:
			self.dataSelect = self.tree.GetItemPyData(evt.GetItem())
		except Exception as e:
			self.dataSelect = None
		
	def refresh( self, events=None ):
		if events is None:
			try:
				d = self.datePicker.GetValue()
				events = GetRaceDBEvents(
					url=self.fixUrl(),
					date=datetime.date( d.GetYear(), d.GetMonth()+1, d.GetDay() ),
				)
			except Exception as e:
				events = {'events':[]}
		
		competitions = {}
		for e in events['events']:
			try:
				competition = competitions[e['competition_name']]
			except KeyError:
				competition = competitions[e['competition_name']] = {
					'num':len(competitions),
					'name':e['competition_name'],
					'participant_count':0,
					'events':[],
				}
			competition['events'].append( e )
			competition['participant_count'] += e['participant_count']
		
		self.tree.DeleteAllItems()
		self.root = self.tree.AddRoot( _('All') )
		self.tree.SetItemText(
			self.root,
			unicode(sum(c['participant_count'] for c in competitions.itervalues())), self.participantCountCol
		)
		
		def get_tod( t ):
			return t.split()[1][:5].lstrip('0')
			
		def get_time( t ):
			return datetime.time( *[int(f) for f in get_tod(t).split(':')] )
			
		tNow = datetime.datetime.now()
		eventClosest = None
		self.dataSelect = None
		
		for cName, events, participant_count, num in sorted(
				((c['name'], c['events'], c['participant_count'], c['num']) for c in competitions.itervalues()), key=lambda x: x[-1] ):
			competition = self.tree.AppendItem( self.root, cName )
			self.tree.SetItemText( competition, unicode(participant_count), self.participantCountCol )
			for e in events:
				eventData = e
				event = self.tree.AppendItem( competition, u'{}: {}'.format(_('Event'), e['name']), data=wx.TreeItemData(eventData) )
				self.tree.SetItemText( event, get_tod(e['date_time']), self.startTimeCol )
				self.tree.SetItemText( event, _('Mass Start') if e['event_type'] == 0 else _('Time Trial'), self.eventTypeCol )
				self.tree.SetItemText( event, unicode(e['participant_count']), self.participantCountCol )
				
				tEvent = datetime.datetime.combine( tNow.date(), get_time(e['date_time']) )
				if eventClosest is None and tEvent > tNow:
					eventClosest = event
					self.dataSelect = eventData
				
				for w in e['waves']:
					wave = self.tree.AppendItem( event, u'{}: {}'.format(_('Wave'), w['name']), data=wx.TreeItemData(eventData) )
					self.tree.SetItemText( wave, unicode(w['participant_count']), self.participantCountCol )
					start_offset = w.get('start_offset',None)
					if start_offset:
						self.tree.SetItemText( wave, '+' + start_offset, self.startTimeCol )
					for cat in w['categories']:
						category = self.tree.AppendItem( wave, cat['name'], data=wx.TreeItemData(eventData) )
						self.tree.SetItemText( category, unicode(cat['participant_count']), self.participantCountCol )
			self.tree.Expand( competition )
						
		self.tree.Expand( self.root )
		if eventClosest:
			self.tree.SelectItem( eventClosest )
			self.tree.Expand( eventClosest )

if __name__ == '__main__':
	events = GetRaceDBEvents()
	print GetRaceDBEvents( date=datetime.date.today() )
	print GetRaceDBEvents( date=datetime.date.today() - datetime.timedelta(days=2) )
	
	app = wx.App(False)
	mainWin = wx.Frame(None,title="CrossMan", size=(1000,400))
	raceDB = RaceDB(mainWin)
	raceDB.refresh( events )
	raceDB.ShowModal()
	#app.MainLoop()
