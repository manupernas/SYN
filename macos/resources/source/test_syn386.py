"""3.8.7 - tests on actual sidebar row builder, not a ghost separate favorites layout."""
import ast
import textwrap
import types
import unittest
from pathlib import Path
import syn

class W:
    def __init__(self, kind, **kwargs):
        self.kind, self.kwargs, self.settings, self.children = kind, kwargs, {}, []
        self.callbacks = {}
    def __getattr__(self, name):
        if name.startswith('set_'):
            return lambda *args: self.settings.__setitem__(name[4:], args[0] if len(args)==1 else args)
        if name == 'add_css_class': return lambda val: self.settings.setdefault('css', []).append(val)
        if name == 'add_controller': return lambda item: self.settings.setdefault('controllers', []).append(item)
        if name == 'append': return lambda child: self.children.append(child)
        if name == 'connect': return lambda sig, fn: self.callbacks.__setitem__(sig, fn)
        raise AttributeError(name)

class GtkFake:
    Orientation = types.SimpleNamespace(HORIZONTAL='H', VERTICAL='V')
    Align = types.SimpleNamespace(START='start', END='end', FILL='fill', CENTER='center')
    EventSequenceState = types.SimpleNamespace(CLAIMED=1)
    @staticmethod
    def ListBoxRow(): return W('row')
    @staticmethod
    def Box(**kwargs): return W('box', **kwargs)
    @staticmethod
    def Label(**kwargs): return W('label', **kwargs)
    class Image:
        @staticmethod
        def new_from_icon_name(icon): return W('star', icon=icon)
    class GestureClick:
        @staticmethod
        def new(): return W('gesture')

class MainAndFavoritesOneRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = Path(syn.__file__).read_text()
        tree = ast.parse(text)
        method = next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_channel_sidebar_row')
        code = textwrap.dedent(ast.get_source_segment(text, method))
        namespace={'Gtk':GtkFake,
                   'Pango':types.SimpleNamespace(EllipsizeMode=types.SimpleNamespace(END=1)),
                   'GLib':types.SimpleNamespace(idle_add=lambda *args: None),
                   'display_channel_name':syn.display_channel_name, 'tr':syn.tr}
        exec(compile(code,syn.__file__,'exec'),namespace)
        cls.build=staticmethod(namespace['_channel_sidebar_row'])
        cls.src=text

    def make(self, favorite):
        ch=types.SimpleNamespace(name='|ES| LA 1 UHD (4K)',group='ES - TDT',favorite_id='la1')
        pic=W('pill',width=120,height=46)
        fake=types.SimpleNamespace(favorites={'la1'} if favorite else set(),
                                   channel_pill=lambda c,w,h: pic,
                                   toggle_favorite=lambda c: None)
        row=self.build(fake,ch)
        return row

    def test_exactly_same_widget_geometry_in_favorites_and_general(self):
        normal, favored=self.make(False),self.make(True)
        def props(row):
            content=row.settings['child']
            pill,name,star=content.children
            return (content.kwargs,content.settings, pill.kwargs,
                    name.kwargs,name.settings,
                    {k:v for k,v in star.settings.items() if k not in ('tooltip_text','controllers')},star.kind)
        a,b=props(normal),props(favored)
        # Both views differ ONLY in the icon's name, not structure/size/spacing.
        self.assertEqual(a,b)
        self.assertEqual(normal.settings['child'].children[0].kwargs['width'],120)
        self.assertEqual(normal.settings['child'].children[0].kwargs['height'],46)
        self.assertEqual(normal.settings['child'].children[1].kwargs['label'],'LA 1 UHD (4K)')
        self.assertEqual(normal.settings['child'].children[2].settings['pixel_size'],17)

    def test_no_special_favorites_branch_and_no_card(self):
        snippet=self.src[self.src.index('        def render_list(self):'):self.src.index('        def _debug_sidebar_geometry(self):')]
        self.assertIn('row = self._channel_sidebar_row(ch)',snippet)
        self.assertNotIn('if self.favs.get_active():',snippet)
        self.assertNotIn('Gtk.Overlay',snippet)
        self.assertNotIn('_channel_card',self.src)

    def test_image_wont_impose_natural_size(self):
        snippet=self.src[self.src.index('        def channel_pill(self, ch'):self.src.index('        def _channel_sidebar_row(',self.src.index('        def channel_pill(self, ch'))]
        self.assertIn('pic = Gtk.DrawingArea()',snippet)
        self.assertIn('pic.set_size_request(108, 38)',snippet)
        self.assertIn('pic.set_content_width(108)',snippet)
        self.assertIn('pic.set_content_height(38)',snippet)
        self.assertIn('pic.set_draw_func(self._draw_channel_logo)',snippet)
        self.assertIn('image._syn_pixbuf = pix',self.src)

if __name__=='__main__':unittest.main()
