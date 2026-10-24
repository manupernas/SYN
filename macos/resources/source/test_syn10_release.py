"""SYN 1.0: test the root cause of the broken Settings button, palettes and saved options.

The GTK opening test calls the ACTUAL open_settings method against a small recording
widget double. It does not claim to prove real Fedora/Wayland rendering.
"""
import ast
from pathlib import Path
import types
import textwrap
import unittest
from unittest.mock import Mock
try:
    import tinycss2
except ImportError:  # Required only for optional CSS validation tests
    tinycss2=None
import syn

SRC=Path(syn.__file__).read_text()

class Item:
    def __init__(self,s): self.s=s
    def get_string(self): return self.s

class FakeWidget:
    made=[]
    def __init__(self,*args,**kwargs):
        self.args=args; self.kwargs=kwargs; self.children=[]; self.callbacks={}
        self.txt=kwargs.get('label',''); self.options=[];self.sel=0;self.presented=False
        self.value=0
        self.made.append(self)
    def append(self,child):self.children.append(child)
    def set_child(self,child):self.children=[child]
    def add_css_class(self,style):pass
    def connect(self,event,fn): self.callbacks[event]=fn
    def set_text(self,value): self.txt=value
    def get_text(self): return self.txt
    def set_selected(self,value):self.sel=value
    def get_selected(self):return self.sel
    def get_selected_item(self):return Item(self.options[self.sel]) if self.options else None
    def set_value(self,value):self.value=value
    def get_value_as_int(self):return int(self.value)
    def present(self):self.presented=True
    def close(self):self.closed=True
    def __getattr__(self,name):
        if name.startswith('set_'):
            return lambda *_args,**_kwargs:None
        raise AttributeError(name)

class FakeGtk:
    class StringList:
        @staticmethod
        def new(items): return list(items)
    Window=type('Window',(FakeWidget,),{})
    ScrolledWindow=type('ScrolledWindow',(FakeWidget,),{})
    Box=type('Box',(FakeWidget,),{})
    Label=type('Label',(FakeWidget,),{})
    Entry=type('Entry',(FakeWidget,),{})
    PasswordEntry=type('PasswordEntry',(FakeWidget,),{})
    Button=type('Button',(FakeWidget,),{})
    Separator=type('Separator',(FakeWidget,),{})
    Orientation=types.SimpleNamespace(VERTICAL=1,HORIZONTAL=2)
    Align=types.SimpleNamespace(START=1)
    class DropDown:
        @staticmethod
        def new_from_strings(strings):
            w=FakeWidget();w.options=list(strings);return w
    class SpinButton:
        @staticmethod
        def new_with_range(*args):return FakeWidget()

class FakeApp:
    def theme_description(self):return 'Palette OK'
    def apply_theme(self,*args):pass

class FakeController:
    def __init__(self):
        p={'id':'test','name':'TV','type':'xtream','source':'',
           'server':'https://example.invalid','username':'user','password':'secret',
           'format':'m3u8','epg_url':'','favorites':['foo'], 'logo_overrides':{'foo':'bar'}}
        self.profile=p
        self.cfg={'profiles':[p],'selected':'test','theme':'dark','accent_hex':'',
                  'player':{'user_agent':'Predeterminado','hwdec':'Predeterminado',
                  'cache':'Predeterminado','video_sync':'Predeterminado',
                  'demuxer_mb':0,'custom_ua':''}}
        self.profile_picker=FakeWidget()
        self.status=FakeWidget()
        self.favorites={'foo'}
    def get_application(self):return FakeApp()
    def _logo_selected_channel(self):return None
    def load_channels(self):pass

class ReleaseTests(unittest.TestCase):
    def test_translator_never_collides_with_gtk_signal_placeholder(self):
        tree=ast.parse(SRC)
        assert 'from syn_i18n import translate as tr' in SRC
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                             and n.func.id=='_' for n in ast.walk(tree)))
        self.assertGreater(sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                               and n.func.id=='tr' for n in ast.walk(tree)),190)

    def test_actual_settings_button_handler_builds_window(self):
        tree=ast.parse(SRC)
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='open_settings')
        namespace={'Gtk':FakeGtk,'tr':syn.tr,'sources':syn.sources,
                   'normalize_accent_hex':syn.normalize_accent_hex}
        exec(compile(textwrap.dedent(ast.get_source_segment(SRC,node)),syn.__file__,'exec'),namespace)
        obj=FakeController(); FakeWidget.made=[]
        namespace['open_settings'](obj, FakeWidget())
        wins=[w for w in FakeWidget.made if isinstance(w,FakeGtk.Window)]
        self.assertEqual(len(wins),1)
        self.assertTrue(wins[0].presented)
        self.assertIn('Settings' if syn.LANGUAGE.startswith('en') else 'Ajustes',wins[0].kwargs['title'])
        # File/source/profile/player controls were built, not just an empty window.
        self.assertGreater(len(FakeWidget.made),30)

    def test_settings_save_preserves_internal_values_in_english(self):
        import gettext
        catalog=gettext.translation('syn',localedir=str(Path(syn.__file__).parent/'locale'),
                                    languages=['en_US']).gettext
        node=next(n for n in ast.walk(ast.parse(SRC))
                  if isinstance(n,ast.FunctionDef) and n.name=='open_settings')
        saved=[]
        fake_sources=types.SimpleNamespace(validate_profile=lambda profile:None,
                                          save_config=lambda cfg:saved.append(cfg),
                                          next_profile_id=lambda:'NEW')
        namespace={'Gtk':FakeGtk,'tr':catalog,'sources':fake_sources,
                   'normalize_accent_hex':syn.normalize_accent_hex}
        exec(compile(textwrap.dedent(ast.get_source_segment(SRC,node)),syn.__file__,'exec'),namespace)
        obj=FakeController(); FakeWidget.made=[]
        namespace['open_settings'](obj,FakeWidget())
        save=next(w for w in FakeWidget.made if isinstance(w,FakeGtk.Button)
                  and w.kwargs.get('label')=='Save settings')
        save.callbacks['clicked'](save)
        self.assertTrue(saved)
        self.assertEqual(obj.cfg['player']['user_agent'],'Predeterminado')
        self.assertEqual(obj.cfg['player']['hwdec'],'Predeterminado')
        self.assertEqual(obj.cfg['profiles'][0]['type'],'xtream')
        self.assertEqual(obj.cfg['profiles'][0]['favorites'],['foo'])

    def test_dark_palette_dropdown_epg_and_welcome(self):
        css=SRC.split('    DARK_CSS = """',1)[1].split('    """',1)[0]
        for selector in ('popover.background > contents', 'popover.background listview row:selected',
                         'dropdown > button:hover', 'window.syn-settings-window passwordentry',
                         'window.syn-settings-window scrollbar slider', '.syn-guide-program-name',
                         '.syn-guide-search', '.syn-zap-row', '.syn-welcome-card',
                         '.syn-fs-top button', 'window.syn-settings-window button.suggested-action'):
            self.assertIn(selector,css,selector)
        self.assertIn('#edf0f5',css)
        self.assertIn('#252931',css)

    @unittest.skipIf(tinycss2 is None,'optional tinycss2 is not installed')
    def test_css_parses_without_syntax_errors(self):
        for tag in ['TEAL_CSS','BASE_CSS','FAVORITE_GEOMETRY_CSS','LIGHT_CSS','DARK_CSS']:
            raw=SRC.split('    '+tag+' = """',1)[1].split('    """',1)[0]
            rules=tinycss2.parse_stylesheet(raw,skip_whitespace=True,skip_comments=True)
            self.assertFalse([r for r in rules if r.type=='error'],tag)
            self.assertGreaterEqual(len(rules),2,tag)
            for rule in rules:
                if rule.type=='qualified-rule':
                    props=tinycss2.parse_declaration_list(rule.content,skip_whitespace=True,skip_comments=True)
                    self.assertFalse([p for p in props if p.type=='error'],(tag,rule.source_line))

    def test_untouched_player_and_logo_canvas(self):
        import hashlib
        t=ast.parse(SRC)
        core=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='NativeMpv')
        self.assertEqual(hashlib.sha256(ast.dump(core,include_attributes=False).encode()).hexdigest(),
                         'fccf6acdefea0a48051946aa54d796c0877590d3b9e47940753bfe8e598ed19e')
        self.assertIn('pic = Gtk.DrawingArea()', SRC)
        self.assertIn('pic.set_size_request(108, 38)', SRC)

if __name__=='__main__':unittest.main()
