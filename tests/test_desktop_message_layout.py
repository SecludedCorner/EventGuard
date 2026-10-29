"""Mapped Tk long backup receipts must wrap within the actual client width."""
import unittest

import test_desktop_investigation_widgets as fixture


class DesktopMessageLayoutTests(unittest.TestCase):
    setUp = fixture.DesktopInvestigationWidgetTests.setUp
    close_ui = fixture.DesktopInvestigationWidgetTests.close_ui
    wait_for = fixture.DesktopInvestigationWidgetTests.wait_for
    select = fixture.DesktopInvestigationWidgetTests.select

    def find_label(self, variable):
        pending = [self.window]
        while pending:
            widget = pending.pop()
            if widget.winfo_class() == 'TLabel' and str(widget.cget('textvariable')) == str(variable):
                return widget
            pending.extend(widget.winfo_children())
        self.fail('own Tk variable label missing')

    def test_backup_receipt_wraps_after_resize_without_hiding_controls(self):
        self.wait_for(lambda: not self.ui.worker.pending)
        self.select(self.anchor)
        self.ui.history_backup_button.invoke()
        self.wait_for(lambda: '歷程備份已核對' in self.ui.message.get())
        notebook = self.ui.events.master.master
        notebook.select(self.ui.events.master)
        self.window.deiconify()
        for width, height in ((1080, 760), (850, 620)):
            with self.subTest(client=(width, height)):
                self.window.geometry(f'{width}x{height}')
                self.window.update()
                label = self.find_label(self.ui.message)
                self.assertLessEqual(int(label.cget('wraplength')), label.winfo_width())
                self.assertLessEqual(label.winfo_reqheight(), label.winfo_height())
                row = self.ui.events.bbox(self.anchor)
                self.assertTrue(row, 'long message must not hide the selected event')
                self.assertLessEqual(row[1]+row[3], self.ui.events.winfo_height())
                button = self.ui.history_backup_button
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                                     self.window.winfo_rooty()+self.window.winfo_height())
