"""
reqResViewer.py

Copyright 2008 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""
import gtk
import gobject
import pango

from . import entries

# To show request and responses
from core.data.db.reqResDBHandler import reqResDBHandler
from core.data.constants import severity
from core.controllers.w3afException import w3afException

useMozilla = False
useGTKHtml2 = True

try:
    import gtkmozembed
    withMozillaTab = True
except Exception, e:
    withMozillaTab = False

try:
    import gtkhtml2
    withGtkHtml2 = True
except Exception, e:
    withGtkHtml2 = False

# Signal handler to handle SIGSEGV generated by gtkhtml2
import signal

def sigsegv_handler(signum, frame):
    print _('This is a catched segmentation fault!')
    print _('I think you hitted bug #1933524 , this is mainly a gtkhtml2 problem. Please report this error here:')
    print _('https://sourceforge.net/tracker/index.php?func=detail&aid=1933524&group_id=170274&atid=853652')
signal.signal(signal.SIGSEGV, sigsegv_handler)
# End signal handler

class reqResViewer(gtk.VBox):
    """
    A widget with the request and the response inside.

    @author: Andres Riancho ( andres.riancho@gmail.com )
    @author: Facundo Batista ( facundo@taniquetil.com.ar )
    """
    def __init__(self, w3af, enableWidget=None, withManual=True, withFuzzy=True,\
            withCompare=True, editableRequest=False, editableResponse=False, widgname="default"):
        super(reqResViewer,self).__init__()
        self.w3af = w3af

        nb = gtk.Notebook()
        self.pack_start(nb, True, True)
        nb.show()

        # Request
        self.request = requestPart(w3af, enableWidget, editable=editableRequest, widgname=widgname)
        self.request.show()
        nb.append_page(self.request, gtk.Label(_("Request")))

        # Response
        self.response = responsePart(w3af, editable=editableResponse, widgname=widgname)
        self.response.show()
        nb.append_page(self.response, gtk.Label(_("Response")))

        # Buttons
        if withManual or withFuzzy or withCompare:
            from .craftedRequests import ManualRequests, FuzzyRequests
            hbox = gtk.HBox()
            if withManual:
                b = entries.SemiStockButton("", gtk.STOCK_INDEX, _("Send Request to Manual Editor"))
                b.connect("clicked", self._sendRequest, ManualRequests)
                self.request.childButtons.append(b)
                b.show()
                hbox.pack_start(b, False, False, padding=2)
            if withFuzzy:
                b = entries.SemiStockButton("", gtk.STOCK_PROPERTIES, _("Send Request to Fuzzy Editor"))
                b.connect("clicked", self._sendRequest, FuzzyRequests)
                self.request.childButtons.append(b)
                b.show()
                hbox.pack_start(b, False, False, padding=2)
            if withCompare:
                b = entries.SemiStockButton("", gtk.STOCK_ZOOM_100, _("Send Request and Response to Compare Tool"))
                b.connect("clicked", self._sendReqResp)
                self.response.childButtons.append(b)
                b.show()
                hbox.pack_start(b, False, False, padding=2)
            self.pack_start(hbox, False, False, padding=5)
            hbox.show()

        self.show()

    def _sendRequest(self, widg, func):
        """Sends the texts to the manual or fuzzy request.

        @param func: where to send the request.
        """
        headers,data = self.request.getBothTexts()
        func(self.w3af, (headers,data))

    def _sendReqResp(self, widg):
        """Sends the texts to the compare tool."""
        headers,data = self.request.getBothTexts()
        self.w3af.mainwin.commCompareTool((headers, data, self.response.showingResponse))

    def set_sensitive(self, how):
        """Sets the pane on/off."""
        self.request.set_sensitive(how)
        self.response.set_sensitive(how)

class requestResponsePart(gtk.Notebook):
    """Request/response common class."""

    def __init__(self, w3af, enableWidget=None, editable=False, widgname="default"):
        super(requestResponsePart, self).__init__()
        self.childButtons = []
        self._initRawTab(editable)
        self._initHeadersTab(editable)

        if enableWidget:
            self._raw.get_buffer().connect("changed", self._changed, enableWidget)
            for widg in enableWidget:
                widg(False)
        self.show()

    def _initRawTab(self, editable):
        """Init for Raw tab."""
        self._raw = searchableTextView()
        self._raw.set_editable(editable)
        self._raw.set_border_width(5)
        self._raw.show()
        self.append_page(self._raw, gtk.Label("Raw"))

    def _initHeadersTab(self, editable):
        """Init for Headers tab."""
        vbox = gtk.VBox()

        self._headersStore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING,\
                gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)
        self._headersTreeview = gtk.TreeView(self._headersStore)

        # Column for Name
        column = gtk.TreeViewColumn(_('Name'), gtk.CellRendererText(), text=0)
        column.set_sort_column_id(0)
        column.set_resizable(True)
        self._headersTreeview.append_column(column)

        # Column for Value
        renderer = gtk.CellRendererText()
        renderer.set_property( 'editable', True )
        renderer.connect('edited', self._header_edited, self._headersStore)
        column = gtk.TreeViewColumn(_('Value'), renderer, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        column.set_sort_column_id(1)
        self._headersTreeview.append_column(column)

        # Column for Action
        column = gtk.TreeViewColumn(_('Action'))
        # Up
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, False)
        column.set_attributes(renderer, stock_id=2)
        # Down
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, False)
        column.set_attributes(renderer, stock_id=3)
        # Delete
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, False)
        column.set_attributes(renderer, stock_id=4)
        self._headersTreeview.append_column(column)

        self._headersTreeview.show()
        hbox = gtk.HBox()
        nameEntry = gtk.Entry()
        nameEntry.show()
        hbox.pack_start(nameEntry, False, False, padding=2)
        valueEntry = gtk.Entry()
        valueEntry.show()
        hbox.pack_start(valueEntry, False, False, padding=2)
        b = gtk.Button(stock=gtk.STOCK_ADD)
        #b.connect("clicked", self._sendRequest, ManualRequests)
        #self.request.childButtons.append(b)
        b.show()
        hbox.pack_start(b, False, False, padding=2)
        hbox.show()
        vbox.pack_start(self._headersTreeview)
        vbox.pack_start(hbox, False, False)
        vbox.show()
        self.append_page(vbox, gtk.Label("Headers"))

    def _header_edited(self, cell, path, new_text, model):
        print "Change '%s' to '%s'" % (model[path][1], new_text)
        model[path][1] = new_text
        return

    def set_sensitive(self, how):
        """Sets the pane on/off."""
        super(requestResponsePart, self).set_sensitive(how)
        for but in self.childButtons:
            but.set_sensitive(how)

    def _changed(self, widg, toenable):
        """Supervises if the widget has some text."""
        rawBuf = self._raw.get_buffer()
        rawText = rawBuf.get_text(rawBuf.get_start_iter(), rawBuf.get_end_iter())
        for widg in toenable:
            widg(bool(rawText))

    def _clear(self, textView):
        """Clears a text view."""
        buff = textView.get_buffer()
        start, end = buff.get_bounds()
        buff.delete(start, end)

    def clearPanes(self):
        """Public interface to clear both panes."""
        self._clear(self._raw)

    def showError(self, text):
        """Show an error.
        Errors are shown in the upper part, with the lower one greyed out.
        """
        self._clear(self._raw)
        buff = self._raw.get_buffer()
        iter = buff.get_end_iter()
        buff.insert(iter, text)

    def getBothTexts(self):
        """Returns request data as turple headers + data."""
        rawBuf = self._raw.get_buffer()
        rawText = rawBuf.get_text(rawBuf.get_start_iter(), rawBuf.get_end_iter())
        headers = rawText
        data = ""
        tmp = rawText.find("\n\n")

        if tmp != -1:
            headers = rawText[0:tmp+1]
            data = rawText[tmp+2:]
            if data.strip() == "":
                data = ""
        return (headers, data)

    def _to_utf8(self, text):
        """
        This method was added to fix:

        GtkWarning: gtk_text_buffer_emit_insert: assertion `g_utf8_validate (text, len, NULL)'

        @parameter text: A text that may or may not be in UTF-8.
        @return: A text, that's in UTF-8, and can be printed in a text view
        """
        text = repr(text)
        text = text[1:-1]

        for special_char in ['\n', '\r', '\t']:
            text = text.replace( repr(special_char)[1:-1], special_char )

        return text

    def showObject(self, obj):
        raise w3afException('Child MUST implment a showObject method.')

    def _synchronize(self, source=None):
        raise w3afException('Child MUST implment a _synchronize method.')

class requestPart(requestResponsePart):
    """Request part"""

    def showObject(self, fuzzableRequest):
        """Show the data from a fuzzableRequest object in the textViews."""
        self.showingRequest = fuzzableRequest
        head = fuzzableRequest.dumpRequestHead()
        postdata = fuzzableRequest.getData()

        self._clear(self._raw)
        buff = self._raw.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, self._to_utf8(head + "\n\n" + postdata))
        self._updateHeadersTab(fuzzableRequest.getHeaders())

    def _updateHeadersTab(self, headers):
        self._headersStore.clear()
        print headers
        for header in headers:
            self._headersStore.append([header, headers[header], gtk.STOCK_GO_UP,\
                    gtk.STOCK_GO_DOWN, gtk.STOCK_DELETE])

    def rawShow(self, requestresponse, body):
        """Show the raw data."""
        self._clear(self._raw)
        buff = self._raw.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, requestresponse + "\n\n" + body)

class responsePart(requestResponsePart):
    """Response part"""

    def __init__(self, w3af, editable=False, widgname="default"):
        requestResponsePart.__init__(self, w3af, editable=editable, widgname=widgname+"response")
        self.showingResponse = None

        # second page, only there if html renderer available
        self._renderingWidget = None
        if (withMozillaTab and useMozilla) or (withGtkHtml2 and useGTKHtml2):
            if withGtkHtml2 and useGTKHtml2:
                renderWidget = gtkhtml2.View()
                self._renderFunction = self._renderGtkHtml2
            elif withMozillaTab and useMozilla:
                renderWidget = gtkmozembed.MozEmbed()
                self._renderFunction = self._renderMozilla
            else:
                renderWidget = None

            self._renderingWidget = renderWidget
            if renderWidget is not None:
                swRenderedHTML = gtk.ScrolledWindow()
                swRenderedHTML.add(renderWidget)
                self.append_page(swRenderedHTML, gtk.Label(_("Rendered")))
        self.show_all()

    def _renderGtkHtml2(self, body, mimeType, baseURI):
        # It doesn't make sense to render something empty

        if body == '':
            return
        try:
            document = gtkhtml2.Document()
            document.clear()
            document.open_stream(mimeType)
            document.write_stream(body)
            document.close_stream()
            self._renderingWidget.set_document(document)
        except ValueError, ve:
            # I get here when the mime type is an image or something that I can't display
            pass
        except Exception, e:
            print _('This is a catched exception!')
            print _('Exception:'), type(e), str(e)
            print _('I think you hitted bug #1933524 , this is mainly a gtkhtml2 problem. Please report this error here:')
            print _('https://sourceforge.net/tracker/index.php?func=detail&aid=1933524&group_id=170274&atid=853652')

    def _renderMozilla(self, body, mimeType, baseURI):
        self._renderingWidget.render_data(body, long(len(body)), baseURI , mimeType)

    def showObject(self, httpResp):
        """Show the data from a httpResp object in the textViews."""
        self.showingResponse = httpResp
        resp = httpResp.dumpResponseHead()
        body = httpResp.getBody()

        self._clear(self._raw)
        buff = self._raw.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, self._to_utf8(resp + "\n\n" + body))
        self.showParsed("1.1", httpResp.getCode(), httpResp.getMsg(),\
                httpResp.dumpResponseHead(), httpResp.getBody(), httpResp.getURI())

    def showParsed( self, version, code, msg, headers, body, baseURI ):
        """Show the parsed data"""
        # Clear previous results
        #self._clear( self._raw )

        #buff = self._raw.get_buffer()
        #iterl = buff.get_end_iter()
        #buff.insert( iterl, 'HTTP/' + version + ' ' + str(code) + ' ' + str(msg) + '\n')
        #buff.insert( iterl, headers )
        
        # Get the mimeType from the response headers
        mimeType = 'text/html'
        #headers = headers.split('\n')
        #headers = [h for h in headers if h]
        #for h in headers:
        #    h_name, h_value = h.split(':', 1)
        #    if 'content-type' in h_name.lower():
        #        mimeType = h_value.strip()
        #        break
        
        # FIXME: Show images
        if 'image' in mimeType:
            mimeType = 'text/html'
            body = _('The response type is: <i>') + mimeType + _('</i>. w3af is still under development, in the future images will be displayed.')
            
        #buff = self._downTv.get_buffer()
        #iterl = buff.get_end_iter()
        #buff.insert( iterl, body )
        
        # Show it rendered
        if self._renderingWidget is not None:
            self._renderFunction(body, mimeType, baseURI)


    def highlight(self, text, sev=severity.MEDIUM):
        """
        Find the text, and handle highlight.
        @return: None.
        """

        # highlight the response header and body
        for text_buffer in [self._downTv, self._raw]:

            (ini, fin) = text_buffer.get_bounds()
            alltext = text_buffer.get_text(ini, fin)

            # find the positions where the phrase is found
            positions = []
            pos = 0
            while True:
                try:
                    pos = alltext.index(text, pos)
                except ValueError:
                    break
                fin = pos + len(text)
                iterini = text_buffer.get_iter_at_offset(pos)
                iterfin = text_buffer.get_iter_at_offset(fin)
                positions.append((pos, fin, iterini, iterfin))
                pos += 1

            # highlight them all
            for (ini, fin, iterini, iterfin) in positions:
                text_buffer.apply_tag_by_name(sev, iterini, iterfin)

SEVERITY_TO_COLOR={
    severity.INFORMATION: 'green', 
    severity.LOW: 'blue',
    severity.MEDIUM: 'yellow',
    severity.HIGH: 'red'}
SEVERITY_TO_COLOR.setdefault('yellow')

class searchableTextView(gtk.VBox, entries.Searchable):
    """A textview widget that supports searches.

    @author: Andres Riancho ( andres.riancho@gmail.com )
    """
    def __init__(self):
        gtk.VBox.__init__(self)

        # Create the textview where the text is going to be shown
        self.textView = gtk.TextView()
        for sev in SEVERITY_TO_COLOR:
            self.textView.get_buffer().create_tag(sev, background=SEVERITY_TO_COLOR[sev])
        self.textView.show()

        # Scroll where the textView goes
        sw1 = gtk.ScrolledWindow()
        sw1.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw1.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw1.add(self.textView)
        sw1.show()
        self.pack_start(sw1, expand=True, fill=True)
        self.show()

        # Create the search widget
        entries.Searchable.__init__(self, self.textView, small=True)

    def get_bounds(self):
        return self.textView.get_buffer().get_bounds()

    def get_text(self, start,  end):
        return self.textView.get_buffer().get_text(start, end)

    def get_iter_at_offset(self, position):
        return self.textView.get_buffer().get_iter_at_offset(position)

    def apply_tag_by_name(self, tag, start, end):
        return self.textView.get_buffer().apply_tag_by_name(tag, start, end)

    def set_editable(self, e):
        return self.textView.set_editable(e)

    def set_border_width(self, b):
        return self.textView.set_border_width(b)

    def get_buffer(self):
        return self.textView.get_buffer()

class reqResWindow(entries.RememberingWindow):
    """
    A window to show a request/response pair.
    """
    def __init__(self, w3af, request_id, enableWidget=None, withManual=True,
                 withFuzzy=True, withCompare=True, editableRequest=False, 
                 editableResponse=False, widgname="default"):
        # Create the window
        entries.RememberingWindow.__init__(
            self, w3af, "reqResWin", _("w3af - HTTP Request/Response"), "Browsing_the_Knowledge_Base")

        # Create the request response viewer
        rrViewer = reqResViewer(w3af, enableWidget, withManual, withFuzzy, withCompare, editableRequest, editableResponse, widgname)

        # Search the id in the DB
        dbh = reqResDBHandler()
        search_result = dbh.searchById( request_id )
        if len(search_result) == 1:
            request, response = search_result[0]

        # Set
        rrViewer.request.showObject( request )
        rrViewer.response.showObject( response )
        rrViewer.show()
        self.vbox.pack_start(rrViewer)

        # Show the window
        self.show()

