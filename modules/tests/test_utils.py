from unittest import TestCase

from ..utils import load_config, slice_sheet_dates


class TestUtils(TestCase):
    def setUp(self):
        pass

    def test_load_config(self):
        sections = ['MAIN', 'TELEGRAM']
        config = load_config()
        self.assertTrue(config)
        config_sections = config.sections()
        for section in sections:
            self.assertTrue(section in config_sections)

    def test_slice_sheet_dates(self):
        dates = [
            'Ежедневно в 20:00',
            'Ежедневно в 12:00',
            '5/2 Будние дни, в 11:00',
            'понедельник, четверг в 13:30',
            '5/2 Будние дни, в 11:00',
            '5/2 Будние дни, в 18:00',
            'Ежедневно в 13:30 по рем.зоне. Ежедневно в 19:30 по магазину'
        ]
        results = []
        for i, date in enumerate(dates):
            result = slice_sheet_dates(date)
            if i == 0:
                assert len(result[0]) == 7
                assert result[1] == '20:00'
            elif i == 1:
                assert len(result[0]) == 7
                assert result[1] == '12:00'
            elif i == 2:
                assert len(result[0]) == 5
                assert result[1] == '11:00'
            elif i == 3:
                assert len(result[0]) == 2
                assert result[0] == [0, 3]
                assert result[1] == '13:30'
            elif i == 4:
                assert len(result[0]) == 5
                assert result[1] == '11:00'
            print(result)
            results.append(result)
