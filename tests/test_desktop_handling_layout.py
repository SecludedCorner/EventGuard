"""Own mapped Tk geometry/focus traversal; not human or native-input acceptance."""
import unittest

import test_desktop_investigation_widgets as fixture


class DesktopHandlingLayoutTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def test_actions_and_filters_fit_default_and_minimum_client_sizes(self):
        self.select(self.anchor)
        notebook = self.ui.events.master.master
        notebook.select(self.ui.events.master)
        self.window.deiconify()
        for width, height in ((1080, 760), (850, 620)):
            with self.subTest(client=(width, height)):
                self.window.geometry(f'{width}x{height}')
                self.window.update()
                self.assertEqual((self.window.winfo_width(), self.window.winfo_height()), (width, height))
                row = self.ui.events.bbox(self.anchor)
                self.assertTrue(row, 'selected event row must remain visible')
                self.assertLessEqual(row[1]+row[3], self.ui.events.winfo_height())
                self.assertIsNotNone(self.ui.detail.dlineinfo('1.0'), 'detail needs a visible text line')
                for widget in (self.ui.events, self.ui.detail, self.ui.severity_choice,
                               self.ui.delivery_choice, self.ui.handling_choice, self.ui.clear_filters_button,
                               self.ui.investigate_button, self.ui.history_backup_button, self.ui.history_preview_button,
                               *self.ui.handling_buttons.values()):
                    self.assertTrue(widget.winfo_ismapped(), str(widget))
                    self.assertGreater(widget.winfo_height(), 1, str(widget))
                    parent = widget.master
                    while parent is not None:
                        self.assertGreaterEqual(widget.winfo_rootx(), parent.winfo_rootx(), str(widget))
                        self.assertGreaterEqual(widget.winfo_rooty(), parent.winfo_rooty(), str(widget))
                        self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),
                                             parent.winfo_rootx()+parent.winfo_width(), str(widget))
                        self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),
                                             parent.winfo_rooty()+parent.winfo_height(), str(widget))
                        parent = parent.master
                target = str(self.ui.history_backup_button)
                start = current = str(self.ui.handling_choice)
                seen = set()
                while current not in seen:
                    seen.add(current)
                    current = str(self.window.tk.call('tk_focusNext', current))
                self.assertIn(target, seen, f'backup not in Tk traversal from {start}')

    def test_automatic_settings_remain_visible_in_their_own_tab(self):
        notebook = self.ui.automatic_check.master.master
        notebook.select(self.ui.automatic_check.master)
        self.window.deiconify()
        self.window.geometry('850x620')
        self.window.update()
        for widget in (self.ui.automatic_check, self.ui.automatic_path, self.ui.automatic_browse):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),
                                 self.window.winfo_rootx()+self.window.winfo_width())
            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),
                                 self.window.winfo_rooty()+self.window.winfo_height())
