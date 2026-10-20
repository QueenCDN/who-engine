"""Маршрутизация разделов и выдача иконок."""
import unittest

from who_engine.ui.base import PageRouter


class FakePage:
    def __init__(self, label, icon=''):
        self.label = label
        self.icon = icon
        self.rendered = 0

    def render(self):
        self.rendered += 1


class IconlessPage:
    """Раздел без иконки: навигация обязана это пережить."""

    label = 'Без значка'

    def render(self):
        pass


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.first = FakePage('Эксперименты', ':material/science:')
        self.second = FakePage('Архив локально', ':material/library_books:')
        self.router = PageRouter((self.first, self.second))

    def test_labels_keep_declared_order(self):
        self.assertEqual(self.router.labels,
                         ('Эксперименты', 'Архив локально'))

    def test_default_is_first(self):
        self.assertEqual(self.router.default, 'Эксперименты')

    def test_renders_selected_page(self):
        self.router.render('Архив локально')
        self.assertEqual(self.second.rendered, 1)
        self.assertEqual(self.first.rendered, 0)

    def test_unknown_label_falls_back_to_default(self):
        self.router.render('Нет такого раздела')
        self.assertEqual(self.first.rendered, 1)

    def test_icon_comes_from_the_page(self):
        self.assertEqual(self.router.icon('Эксперименты'),
                         ':material/science:')
        self.assertEqual(self.router.icon('Архив локально'),
                         ':material/library_books:')

    def test_page_without_icon_gives_none(self):
        router = PageRouter((IconlessPage(),))
        self.assertIsNone(router.icon('Без значка'))

    def test_unknown_label_has_no_icon(self):
        self.assertIsNone(self.router.icon('Нет такого раздела'))

    def test_empty_router_is_rejected(self):
        with self.assertRaises(ValueError):
            PageRouter(())


if __name__ == '__main__':
    unittest.main()
