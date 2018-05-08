from abc import ABCMeta
import os

from .sampler import Sampler
from ..sequences import Genome
from ..targets import GenomicFeatures
from ..utils import load_features_list

class OnlineSampler(Sampler, metaclass=ABCMeta):
    """
    A sampler in which training/validation/test data is constructed from
    random sampling of the dataset for each batch passed to the model.
    This form of sampling may alleviate the problem of loading an
    extremely large dataset into memory when developing a new model.
    """
    STRAND_SIDES = ('+', '-')

    def __init__(self,
                 genome,
                 query_feature_data,
                 distinct_features,
                 random_seed=436,
                 validation_holdout=['6', '7'],
                 test_holdout=['8', '9'],
                 sequence_length=1000,
                 center_bin_to_predict=200,
                 feature_thresholds=0.5,
                 mode="train",
                 save_datasets=["test"]):
        """@TODO: This is specific to Genome/GenomicFeatures. Is there a way
        to make this idea more general in the future?

        Parameters
        ----------
        genome : str
            Path to indexed FASTA file
        query_feature_data : str
            Path to tabix-indexed, compressed BED file (*.bed.gz) of genomic
            coordinates mapped to the genomic features we want to predict.
        distinct_features : str
            Path to the distinct list of genomic features we want to predict.
        random_seed : int, optional
            Default is 436. Set the random seed for sampling.
        validation_holdout : list of str or float, optional
            Default is ['6', '7']. Holdout can be chromosomal or proportional.
            If chromosomal, expects a list (e.g. ['X', 'Y']). Chromosomes
            must match those specified in the first column of the
            tabix-indexed BED file. If proportional, specify a percentage
            between (0.0, 1.0). Typically 0.10 or 0.20.
        test_holdout : list of str or float, optional
            Default is ['8', '9']. See documentation for `validation_holdout`.
        sequence_length : int, optional
            Default is 1000. Model is trained on sequences of `sequence_length`
            where genomic features are annotated to the center regions of
            these sequences.
        center_bin_to_predict : int, optional
            Default is 200. Query the tabix-indexed file for a region of
            length `center_bin_to_predict`.
        feature_thresholds : float [0.0, 1.0], optional
        mode : {"train", "validate", "test"}
        save_datasets : list of str
            Default is ["test"].
        """
        super(OnlineSampler, self).__init__(
            random_seed=random_seed
        )

        if (sequence_length + center_bin_to_predict) % 2 != 0:
            raise ValueError(
                "Sequence length of {0} with a center bin length of {1} "
                "is invalid. These 2 inputs should both be odd or both be "
                "even.".format(
                    sequence_length, center_bin_to_predict))

        surrounding_sequence_length = \
            sequence_length - center_bin_to_predict
        if surrounding_sequence_length < 0:
            raise ValueError(
                "Sequence length of {0} is less than the center bin "
                "length of {1}.".format(
                    sequence_length, center_bin_to_predict))

        # specifying a test holdout partition is optional
        if test_holdout:
            self.modes.append("test")
            if isinstance(validation_holdout, (list,)) and \
                    isinstance(test_holdout, (list,)):
                self.validation_holdout = [
                    str(c) for c in validation_holdout]
                self.test_holdout = [str(c) for c in test_holdout]
                self._holdout_type = "chromosome"
            elif isinstance(validation_holdout, float) and \
                    isinstance(test_holdout, float):
                self.validation_holdout = validation_holdout
                self.test_holdout = test_holdout
                self._holdout_type = "proportion"
            else:
                raise ValueError(
                    "Validation holdout and test holdout must have the "
                    "same type (list or float) but validation was "
                    "type {0} and test was type {1}".format(
                        type(validation_holdout), type(test_holdout)))
        else:
            self.test_holdout = None
            if isinstance(validation_holdout, (list,)):
                self.validation_holdout = [
                    str(c) for c in validation_holdout]
            else:
                self.validation_holdout = validation_holdout

        if mode not in self.modes:
            raise ValueError(
                "Mode must be one of {0}. Input was '{1}'.".format(
                    self.modes, mode))
        self.mode = mode

        self.surrounding_sequence_radius = int(
            surrounding_sequence_length / 2)
        self.sequence_length = sequence_length
        self.bin_radius = int(center_bin_to_predict / 2)
        self._start_radius = self.bin_radius
        if center_bin_to_predict % 2 == 0:
            self._end_radius = self.bin_radius
        else:
            self._end_radius = self.bin_radius + 1

        self.genome = Genome(genome)

        self._features = load_features_list(distinct_features)
        self.n_features = len(self._features)

        self.query_feature_data = GenomicFeatures(
            query_feature_data, self._features,
            feature_thresholds=feature_thresholds)

        self.save_datasets = {}
        for mode in save_datasets:
            self.save_datasets[mode] = []

    def get_feature_from_index(self, feature_index):
        """Returns the feature corresponding to an index in the feature
        vector.

        Parameters
        ----------
        feature_index : int

        Returns
        -------
        str
        """
        return self.query_feature_data.index_feature_map[feature_index]

    def get_sequence_from_encoding(self, encoding):
        """Gets the string sequence from the one-hot encoding
        of the sequence.

        Parameters
        ----------
        encoding : numpy.ndarray
            The one-hot encoding of the sequence

        Returns
        -------
        str
        """
        return self.genome.encoding_to_sequence(encoding)

    def save_datasets_to_file(self, output_dir):
        """This likely only works for validation and test right now.
        Training data may be too big to store in a list in memory, so
        it is a @TODO to be able to save training data coordinates
        intermittently.

        Save samples for each partition (train/validate/tests) to file.

        Parameters
        ----------
        output_dir : str
            Path to the output directory to which we should save the datasets.
        """
        for mode, samples in self.save_datasets.items():
            filepath = os.path.join(output_dir, f"{mode}_data.bed")
            with open(filepath, 'w+') as file_handle:
                for cols in samples:
                    line ='\t'.join([str(c) for c in cols])
                    file_handle.write(f"{line}\n")