import unittest

import numpy as np
import torch
import torch.nn as nn
from scipy.sparse import csr_matrix

from snorkel.labeling.model.label_model import LabelModel


class LabelModelTest(unittest.TestCase):
    def _set_up_model(self, L, deps=[], class_balance=[0.5, 0.5]):
        label_model = LabelModel(k=2, verbose=False)
        label_model._set_constants(L)
        label_model._set_dependencies(deps=deps)
        label_model._generate_O(L)
        label_model._build_mask()
        label_model._get_augmented_label_matrix(L, higher_order=True)
        label_model.inv_form = len(deps) > 0
        label_model._set_class_balance(class_balance=class_balance, Y_dev=None)
        label_model._init_params()

        return label_model

    def test_L_form(self):
        label_model = LabelModel(k=2, verbose=False)

        # Test dimension constants
        L = np.array([[1, 2, 1], [1, 0, 1], [2, 1, 1], [1, 2, -1]])
        L_sparse = csr_matrix(L)
        with self.assertRaises(ValueError):
            label_model._check_L(L_sparse)

        L = np.array([[1, 2, 1], [1, 2, 1], [2, 1, 1], [1, 2, 1]])
        label_model._set_constants(L)
        self.assertEqual(label_model.n, 4)
        self.assertEqual(label_model.m, 3)

    def test_class_balance(self):
        label_model = LabelModel(k=2, verbose=False)

        # Test class balance
        Y_dev = np.array([1, 1, 2, 2, 1, 1, 1, 1, 2, 2])
        label_model._set_class_balance(class_balance=None, Y_dev=Y_dev)
        np.testing.assert_array_almost_equal(label_model.p, np.array([0.6, 0.4]))

    def test_generate_O(self):
        L = np.array([[1, 2, 1], [1, 2, 1], [2, 1, 1], [1, 2, 2]])
        label_model = self._set_up_model(L)

        true_O = np.array(
            [
                [3 / 4, 0, 0, 3 / 4, 1.0 / 2, 1 / 4],
                [0, 1 / 4, 1 / 4, 0, 1 / 4, 0],
                [0, 1 / 4, 1 / 4, 0, 1 / 4, 0],
                [3 / 4, 0, 0, 3 / 4, 1 / 2, 1 / 4],
                [1 / 2, 1 / 4, 1 / 4, 1 / 2, 3 / 4, 0],
                [1 / 4, 0, 0, 1 / 4, 0, 1 / 4],
            ]
        )
        np.testing.assert_array_almost_equal(label_model.O.numpy(), true_O)

    def test_augmented_L_construction(self):
        # 5 LFs: a triangle, a connected edge to it, and a singleton source
        n = 3
        m = 5
        k = 2
        E = [(0, 1), (1, 2), (2, 0), (0, 3)]
        L = np.array([[1, 1, 1, 2, 1], [1, 2, 2, 1, 0], [1, 1, 1, 1, 0]])
        lm = LabelModel(k=k, verbose=False)
        lm._set_constants(L)
        lm._set_dependencies(E)
        L_aug = lm._get_augmented_label_matrix(L, higher_order=True)

        # Should have 22 columns:
        # - 5 * 2 = 10 for the sources
        # - 8 + 4 for the 3- and 2-clique resp. --> = 22
        self.assertEqual(L_aug.shape, (3, 22))

        # Same as above but minus 2 abstains = 19 total nonzero entries
        self.assertEqual(L_aug.sum(), 19)

        # Next, check the singleton entries
        for i in range(n):
            for j in range(m):
                if L[i, j] > 0:
                    self.assertEqual(L_aug[i, j * k + L[i, j] - 1], 1)

        # Finally, check the clique entries
        # Triangle clique
        self.assertEqual(len(lm.c_tree.node[1]["members"]), 3)
        j = lm.c_tree.node[1]["start_index"]
        self.assertEqual(L_aug[0, j], 1)
        self.assertEqual(L_aug[1, j + 3], 1)
        self.assertEqual(L_aug[2, j], 1)
        # Binary clique
        self.assertEqual(len(lm.c_tree.node[2]["members"]), 2)
        j = lm.c_tree.node[2]["start_index"]
        self.assertEqual(L_aug[0, j + 1], 1)
        self.assertEqual(L_aug[1, j], 1)
        self.assertEqual(L_aug[2, j], 1)

    def test_conditional_probs(self):
        L = np.array([[1, 2, 1], [1, 2, 1]])
        label_model = self._set_up_model(L, class_balance=[0.6, 0.4])
        probs = label_model.get_conditional_probs()
        self.assertLessEqual(probs.max(), 1.0)
        self.assertGreaterEqual(probs.min(), 0.0)

    def test_get_accuracy(self):
        L = np.array([[1, 2], [1, 0]])
        label_model = self._set_up_model(L)
        probs = np.array(
            [
                [0.99, 0.01],
                [0.5, 0.5],
                [0.9, 0.9],
                [0.99, 0.01],
                [0.9, 0.9],
                [0.5, 0.75],
                [0.9, 0.9],
                [0.9, 0.1],
            ]
        )

        label_model.m = 2
        label_model.k = 2
        label_model.P = torch.Tensor([[0.5, 0.0], [0.0, 0.5]])
        accs = label_model.get_accuracies(probs=probs)
        np.testing.assert_array_almost_equal(accs, np.array([0.7, 0.825]))

        label_model.mu = nn.Parameter(label_model.mu_init.clone())
        accs = label_model.get_accuracies(probs=None)
        np.testing.assert_array_almost_equal(accs, np.array([0.5, 0.355]))

    def test_build_mask(self):

        L = np.array([[1, 2, 1], [1, 2, 1]])
        label_model = self._set_up_model(L)

        true_mask = np.array(
            [
                [0, 0, 1, 1, 1, 1],
                [0, 0, 1, 1, 1, 1],
                [1, 1, 0, 0, 1, 1],
                [1, 1, 0, 0, 1, 1],
                [1, 1, 1, 1, 0, 0],
                [1, 1, 1, 1, 0, 0],
            ]
        )

        mask = label_model.mask.numpy()
        np.testing.assert_array_equal(mask, true_mask)

        label_model = self._set_up_model(L, deps=[(1, 2)])
        true_mask = np.array(
            [
                [0, 0, 1, 1, 1, 1],
                [0, 0, 1, 1, 1, 1],
                [1, 1, 0, 0, 0, 0],
                [1, 1, 0, 0, 0, 0],
                [1, 1, 0, 0, 0, 0],
                [1, 1, 0, 0, 0, 0],
            ]
        )

        mask = label_model.mask.numpy()
        np.testing.assert_array_equal(mask, true_mask)

    def test_init_params(self):
        L = np.array([[1, 2, 1], [1, 0, 1]])
        label_model = self._set_up_model(L, class_balance=[0.6, 0.4])

        mu_init = label_model.mu_init.numpy()
        true_mu_init = np.array(
            [[1.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.8750], [1.0, 0.0], [0.0, 0.0]]
        )
        np.testing.assert_array_equal(mu_init, true_mu_init)

        label_model._set_class_balance(class_balance=[0.3, 0.7], Y_dev=None)
        label_model._init_params()

        mu_init = label_model.mu_init.numpy()
        true_mu_init = np.array(
            [[1.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.5], [1.0, 0.0], [0.0, 0.0]]
        )
        np.testing.assert_array_equal(mu_init, true_mu_init)

    def test_predict_proba(self):
        L = np.array([[1, 2, 1], [1, 2, 1]])
        label_model = self._set_up_model(L)

        label_model.mu = nn.Parameter(label_model.mu_init.clone())
        probs = label_model.predict_proba(L)

        true_probs = np.array([[0.99, 0.01], [0.99, 0.01]])
        np.testing.assert_array_almost_equal(probs, true_probs)

        L = np.array([[1, 2, 1], [1, 2, 0]])
        label_model = self._set_up_model(L, deps=[(1, 2)])
        label_model._get_augmented_label_matrix(L, higher_order=True)

        label_model.mu = nn.Parameter(label_model.mu_init.clone())
        probs = label_model.predict_proba(L)

        true_probs = np.array([0.99, 0.01])
        np.testing.assert_array_almost_equal(probs[1, :], true_probs)

    def test_loss(self):
        L = np.array([[1, 0, 1], [1, 2, 0]])
        label_model = self._set_up_model(L)
        label_model._get_augmented_label_matrix(L, higher_order=True)

        label_model.mu = nn.Parameter(label_model.mu_init.clone() + 0.05)
        self.assertAlmostEqual(
            label_model.loss_l2(l2=1.0).detach().numpy().ravel()[0], 0.03
        )
        self.assertAlmostEqual(
            label_model.loss_l2(l2=np.ones(6)).detach().numpy().ravel()[0], 0.03
        )
        self.assertAlmostEqual(
            label_model.loss_mu().detach().numpy().ravel()[0], 0.675, 3
        )

    def test_inv_loss(self):
        L = np.array([[1, 0, 1], [1, 2, 1]])
        label_model = self._set_up_model(L, deps=[(1, 2)])
        label_model.inv_form = True

        label_model.Z = nn.Parameter(torch.ones(label_model.d, label_model.k)).float()

        Q = label_model.get_Q()
        self.assertAlmostEqual(Q[0, 0], 0.893, 3)

        with self.assertRaises(ValueError):
            label_model.train_model(L, n_epochs=1, prec_init=np.array([1, 0.3]))

        label_model.train_model(L, n_epochs=1, prec_init=1.0)
        self.assertAlmostEqual(label_model.prec_init.detach().numpy().ravel()[0], 1.0)

    def test_loss_decrease(self):
        L = np.array([[1, 0, 1], [1, 2, 1]])
        label_model = self._set_up_model(L)

        label_model.train_model(L, n_epochs=1)
        init_loss = label_model.loss_mu().detach().numpy().ravel()[0]

        label_model.train_model(L, n_epochs=10)
        next_loss = label_model.loss_mu().detach().numpy().ravel()[0]

        self.assertLessEqual(next_loss, init_loss)


if __name__ == "__main__":
    unittest.main()
