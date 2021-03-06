import  wx
from  ExportGrid import ExportGrid

#----------------------------------------------------------------------

class SeriesMgrPrintout(wx.Printout):
	def __init__(self, title, grid):
		wx.Printout.__init__(self)
		self.title = title
		self.grid = grid

	def HasPage(self, page):
		return page == 1

	def GetPageInfo(self):
		return (1,1,1,1)

	def OnPrintPage(self, page):
		exportGrid = ExportGrid( self.title, self.grid )
		dc = self.GetDC()
		exportGrid.drawToFitDC( dc )
		return True
