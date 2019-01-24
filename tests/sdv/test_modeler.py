from unittest import TestCase, mock, skip

import numpy as np
import pandas as pd
from copulas.univariate.kde import KDEUnivariate

from sdv.data_navigator import CSVDataLoader
from sdv.modeler import Modeler


class ModelerTest(TestCase):

    def setUp(self):
        """Set up test fixtures, if any."""
        dl = CSVDataLoader('tests/data/meta.json')
        self.dn = dl.load_data()
        self.dn.transform_data()
        self.modeler = Modeler(self.dn)

    def test__create_extension(self):
        """Tests that the create extension method returns correct parameters."""
        # Setup
        child_table = self.dn.get_data('DEMO_ORDERS')
        user = child_table[child_table['CUSTOMER_ID'] == 50]
        expected = pd.Series([
            1.500000e+00, 0.000000e+00, -1.269991e+00,
            0.000000e+00, 0.000000e+00, 0.000000e+00,
            -1.269991e+00, 0.000000e+00, 1.500000e+00,
            0.000000e+00, 0.000000e+00, -7.401487e-17,
            1.000000e+00, 7.000000e+00, 2.449490e+00,
            4.000000e+00, 5.000000e+01, 5.000000e+01,
            1.000000e-03, 5.000000e+01, 7.300000e+02,
            2.380000e+03, 7.618545e+02, 1.806667e+03
        ])

        # Run
        parameters = self.modeler._create_extension(user, child_table)

        # Check
        assert expected.subtract(parameters).all() < 10E-3

    def test__get_extensions(self):
        """_get_extensions returns a works for table with child"""
        # Setup
        pk = 'ORDER_ID'
        table = 'DEMO_ORDERS'
        children = self.dn.get_children(table)

        # Run
        result = self.modeler._get_extensions(pk, children, table)

        # Check
        assert len(result) == 1
        assert result[0].shape == (10, 35)

    def test_get_extensions_no_children(self):
        """Tests that get extensions works for table with no children."""
        # Setup
        pk = 'ORDER_ITEM_ID'
        table = 'DEMO_ORDER_ITEMS'
        children = self.dn.get_children(table)
        expected_result = []

        # Run
        result = self.modeler._get_extensions(pk, children, table)

        # Check
        assert result == expected_result

    def test_CPA(self):
        """ """
        # Setup
        self.modeler.model_database()
        table_name = 'DEMO_CUSTOMERS'

        # Run
        self.modeler.CPA(table_name)

        # Check
        for name, table in self.modeler.tables.items():
            with self.subTest(table=name):
                raw_table = self.modeler.dn.tables[name].data

                # When we run Conditional Parameter Aggregation we add a key on Modeler.tables
                # for each table. It contains a not null pandas DataFrame with the computed
                # extension.
                assert isinstance(table, pd.DataFrame)

                assert raw_table.shape[0] == table.shape[0]
                assert (raw_table.index == table.index).all()
                assert all([column in table.columns for column in raw_table.columns])

    def test_flatten_model(self):
        """flatten_model returns a pandas.Series with all the params to recreate a model."""
        # Setup
        for data in self.dn.transformed_data.values():
            num_columns = data.shape[1]
            model = self.modeler.model()
            model.fit(data)

            # We generate it this way because RDT behavior is not fully deterministic
            # and transformed data can change between test runs.
            distribs_values = np.array([
                [col_model.std, col_model.mean]
                for col_model in model.distribs.values()
            ]).flatten()

            expected_result = pd.Series(
                list(model.covariance.flatten()) +
                list(distribs_values)
            )

            # Run
            result = self.modeler.flatten_model(model)

            # Check
            assert (result == expected_result).all()
            assert len(result) == num_columns ** 2 + (2 * num_columns)

    def test_impute_table(self):
        """impute_table fills all NaN values with 0 or the mean of values."""
        # Setup
        table = pd.DataFrame([
            {'A': np.nan, 'B': 10., 'C': 20.},
            {'A': 5., 'B': np.nan, 'C': 20.},
            {'A': 5., 'B': 10., 'C': np.nan},
        ])
        expected_result = pd.DataFrame([
            {'A': 5., 'B': 10., 'C': 20.},
            {'A': 5., 'B': 10., 'C': 20.},
            {'A': 5., 'B': 10., 'C': 20.},
        ])

        # Run
        result = self.modeler.impute_table(table)

        # Check
        assert result.equals(expected_result)

        # No null values are left
        assert not result.isnull().all().all()

        # Averages are computed on every column
        for column in result:
            assert 0 not in result[column].values

    def test_model_database(self):
        """model_database computes conditions between tables and models them."""

        # Run
        self.modeler.model_database()

        # Check
        assert self.modeler.tables.keys() == self.modeler.models.keys()

    def test_get_foreign_key(self):
        """get_foreign_key returns the foreign key from a metadata and a primary key."""
        # Setup
        fields = self.modeler.dn.get_meta_data('DEMO_ORDERS')['fields']
        primary = 'CUSTOMER_ID'
        expected_result = 'CUSTOMER_ID'

        # Run
        result = self.modeler.get_foreign_key(fields, primary)

        # Check
        assert result == expected_result

    def test_fit_model_distribution_arg(self):
        """fit_model will pass self.distribution FQN to modeler."""
        # Setup
        model_mock = mock.MagicMock()
        modeler = Modeler(data_navigator='navigator', model=model_mock, distribution=KDEUnivariate)
        data = pd.DataFrame({
            'column': [0, 1, 1, 1, 0],
        })

        # Run
        modeler.fit_model(data)

        # Check
        model_mock.assert_called_once_with(distribution='copulas.univariate.kde.KDEUnivariate')

    @skip('Work in Progress')
    def test_model_database_distribution_arg(self):
        """model_database will use self.distribution to model tables."""
        # Setup
        modeler = Modeler(data_navigator=self.dn, distribution=KDEUnivariate)

        # Run
        modeler.model_database()

        # Check
        assert True

    def test__flatten_dict_flat_dict(self):
        """_flatten_dict don't modify flat dicts."""
        # Setup
        nested_dict = {
            'a': 1,
            'b': 2
        }
        expected_result = {
            'a': 1,
            'b': 2
        }

        # Run
        result = Modeler._flatten_dict(nested_dict)

        # Check
        assert result == expected_result

    def test__flatten_dict_nested_dict(self):
        """_flatten_dict flatten nested dicts respecting the prefixes."""
        # Setup
        nested_dict = {
            'first_key': {
                'a': 1,
                'b': 2
            },
            'second_key': {
                'x': 0
            }
        }

        expected_result = {
            'first_key__a': 1,
            'first_key__b': 2,
            'second_key__x': 0
        }

        # Run
        result = Modeler._flatten_dict(nested_dict)

        # Check
        assert result == expected_result

    def test__flatten_array_ndarray(self):
        """_flatten_array return a dict formed from the input np.array"""
        # Setup
        nested = np.array([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ])
        expected_result = {
            '0__0': 1,
            '0__1': 0,
            '0__2': 0,
            '1__0': 0,
            '1__1': 1,
            '1__2': 0,
            '2__0': 0,
            '2__1': 0,
            '2__2': 1
        }

        # Run
        result = Modeler._flatten_array(nested)

        # Check
        assert result == expected_result

    def test__flatten_array_list(self):
        """_flatten_array return a dict formed from the input list"""
        # Setup
        nested = [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ]
        expected_result = {
            '0__0': 1,
            '0__1': 0,
            '0__2': 0,
            '1__0': 0,
            '1__1': 1,
            '1__2': 0,
            '2__0': 0,
            '2__1': 0,
            '2__2': 1
        }

        # Run
        result = Modeler._flatten_array(nested)

        # Check
        assert result == expected_result
