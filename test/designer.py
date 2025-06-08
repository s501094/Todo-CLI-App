import wx

class MyFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Designer Window", size=(400, 300))
        panel = wx.Panel(self)
        wx.StaticText(panel, label="Designer Loaded", pos=(20, 20))

if __name__ == '__main__':
    app = wx.App(False)
    frame = MyFrame()
    frame.Show()
    app.MainLoop()