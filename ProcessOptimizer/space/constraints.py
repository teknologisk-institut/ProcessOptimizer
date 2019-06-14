from sklearn.utils import check_random_state
from sklearn.utils.fixes import sp_version
from .space import Real, Integer, Categorical
import numpy as np
class Constraints:
    def __init__(self, constraints_list,space):
        """Constraints used when sampling for the aqcuisiiton function

        Parameters
        ----------
        * `constraints_list` [list]:
            A list of constraint objects.

        * `space` [Space]:
            A Space object.
        """

        check_constraints(space,constraints_list) # Check that all constraints are valid
        self.space = space
        # Lists that keep track of which dimensions has which constraints 
        self.single = [None for _ in range(space.n_dims)]
        self.inclusive = [[] for _ in range(space.n_dims)]
        self.exclusive = [[] for _ in range(space.n_dims)]
        self.constraints_list = constraints_list # A copy of the list of constraints
        # Append constraints to the lists
        for constraint in constraints_list:
            if isinstance(constraint,Single):
               self.single[constraint.dimension] = constraint
            elif isinstance(constraint,Inclusive):
                self.inclusive[constraint.dimension].append(constraint)
            elif isinstance(constraint,Exclusive):
                self.exclusive[constraint.dimension].append(constraint)

    def __eq__(self, other):
        if isinstance(other,Constraints):
            return self.constraints_list == other.constraints_list
        else:
            return False

    def rvs(self, n_samples = 1, random_state = None):
        """Draw random samples that all are valid with regards to the constraints.

        The samples are in the original space. They need to be transformed
        before being passed to a model or minimizer by `space.transform()`.

        Parameters
        ----------
        * `n_samples` [int, default=1]:
            Number of samples to be drawn from the space.

        * `random_state` [int, RandomState instance, or None (default)]:
            Set random state to something other than None for reproducible
            results.

        Returns
        -------
        * `points`: [list of lists, shape=(n_points, n_dims)]
           Points sampled from the space.
        """

        rng = check_random_state(random_state)
        rows  = [] # A list of the samples drawn
        n_samples_candidates = 0 # Number of candidates for samples that have been checked

        while len(rows) < n_samples: # We keep sampling until all samples a valid with regard to the constraints
            columns = []
            for i in range(self.space.n_dims): # Iterate through all dimensions
                dim = self.space.dimensions[i]
                if self.single[i]: # If a dimension has a "Single"-type constraint we just sample that value
                    column = np.full(n_samples, self.single[i].value)
                else: # Using the default rvs() for the given dimension
                    if sp_version < (0, 16):
                        column = (dim.rvs(n_samples=n_samples))
                    else:
                        column = (dim.rvs(n_samples=n_samples, random_state=rng))
                columns.append(column)

            # Transpose
            for i in range(n_samples):
                r = []
                for j in range(self.space.n_dims):
                    r.append(columns[j][i])
                if self.validate_sample(r): # For each individual sample we check that it is valid
                    # We only append if it is valid
                    rows.append(r)

            n_samples_candidates += n_samples
            if n_samples_candidates > 10000 and len(rows) == 0:
                # If we have tried with over 10000 samples and still not found a single valid one
                # we throw an error
                raise RuntimeError('Could not find valid samples with constraints {}'.format(self))

        # We draw more samples when needed so we only return n_samples of the samples
        return rows[:n_samples]

    def validate_sample(self,sample):
        """ Validates a sample of of parameter values in regards to the constraints
        Parameters
        ----------
        * `sample`:
            A list of values from each dimension to be checked
        * `constraints`

        """
        """Validates a sample of of parameter values in regards to the constraints

        Parameters
        ----------
        * `sample` [list]:
            A list of values for which validity is checked.

        Returns
        -------
        * `is_valid`: [bool]
           Bool is true if samples are valid. Else None.
        """

        for dim in range(len(sample)): # We iterate through all samples which corresponds to number of dimensions.
            
            # Single constraints.
            if self.single[dim]:
                if not self.single[dim].validate_constraints(sample[dim]):
                    return False

            # Inclusive constraints.
            if self.inclusive[dim]: # Check if there is a least one inclusive constraint.
                # We go through all inlcusive constraints for this dimension and if the value is not found to be included in any
                # of the bounds of the inclusive constraints we return false.
                value_is_valid = False
                for constraint in self.inclusive[dim]:
                    if constraint.validate_constraints(sample[dim]):
                        value_is_valid = True
                        break
                if not value_is_valid:
                    return False

            # Exclusive constraints
            for constraint in self.exclusive[dim]:
                # The first time a value is inside of the exlcuded bounds of the exclusive constraint we return false.
                if not constraint.validate_constraints(sample[dim]):
                    return False

        # If we we did not find any violaiton of the constraints we return True.
        return True

    def __repr__(self):
        return "Constraints({})".format(self.constraints_list)

class Single:
    def __init__(self, dimension, value, dimension_type):
        """Constraint class of type Single.

        This constraint enforces that all values drawn for the specified dimension equals `value`

        Parameters
        ----------
        * `dimension` [int]:
            The index of the dimension for which constraint should be applied.

        * `value` [int, float or str]:
            The enforced value for the constraint.

        * `dimension_type` [str]:
            The type of dimension. Can be 'integer','real' or 'categorical.
            Should be the same type as the dimension it is applied to.
        """

        # Validating input parameters
        if dimension_type == 'categorical':
            if not (type(value) == int or type(value) == str or type(value) == float):
                raise TypeError('Single categorical constraint must be of type int, float or str. Got {}'.format(type(value)))
        elif dimension_type == 'integer':
            if not type(value) == int:
                raise TypeError('Single integer constraint must be of type int. Got {}'.format(type(value)))
        elif dimension_type == 'real':
            if not type(value) == float:
                raise TypeError('Single real constraint must be of type float. Got {}'.format(type(value)))
        else:
            raise ValueError('`dimension_type` must be a string containing "categorical", "integer" or "real". got {}'.format(dimension_type))
        if not (type(dimension) == int):
            raise TypeError('Constraint dimension must be of type int. Got type {}'.format(type(dimension)))
        if not dimension >=0:
            raise ValueError('Dimension can not be a negative number')

        self.value = value
        self.dimension = dimension
        self.dimension_type = dimension_type
        self.validate_constraints = self._validate_constraint

    def _validate_constraint(self, value):
        # Compares value with constraint.
        if value == self.value:
            return True
        else:
            return False

    def __repr__(self):
        return "Single(dimension={}, value={}, dimension_type={})".format(self.dimension, self.value, self.dimension_type)

    def __eq__(self, other):
        if isinstance(other,Single):
            return self.value == other.value and self.dimension == other.dimension and self.dimension_type == other.dimension_type
        else:
            return False

class Bound_Constraint():
    """Base class for Exclusive and Inclusive constraints"""

    def __init__(self, dimension, bounds, dimension_type):
        # Validating input parameters
        if not type(bounds) == tuple and not type(bounds) == list:
            raise TypeError('Bounds should be a tuple or a list. Got {}'.format(type(bounds)))
        if not len(bounds) >1:
            raise ValueError('Bounds should be a tuple or list of length > 1.')
        if not dimension_type == 'categorical':
            if not len(bounds) == 2:
                raise ValueError('Length of bounds must be 2 for non-categorical constraints. Got {}'.format(len(bounds)))
        for bound in bounds:
            if dimension_type == 'integer':
                if not type(bound) == int:
                   raise TypeError('Bounds must be of type int for integer dimension. Got {}'.format(type(bound)))
            elif dimension_type == 'real':
                if not type(bound) == float:
                   raise TypeError('Bounds must be of type float for real dimension. Got {}'.format(type(bound)))
        if not (dimension_type == 'categorical' or dimension_type == 'integer' or dimension_type == 'real'):
            raise ValueError('`dimension_type` must be a string containing "categorical", "integer" or "real". Got {}'.format(dimension_type))
        if not (type(dimension) == int):
            raise TypeError('Constraint dimension must be of type int. Got type {}'.format(type(dimension)))
        if not dimension >=0:
            raise ValueError('Dimension can not be a negative number')

        self.bounds = tuple(bounds) # Convert bounds to a tuple
        self.dimension = dimension
        self.dimension_type = dimension_type

class Inclusive(Bound_Constraint):
    def __init__(self, dimension, bounds,dimension_type):
        super().__init__(dimension, bounds, dimension_type) 
        """Constraint class of type Inclusive.

        This constraint enforces that all values drawn for the specified dimension are inside the bounds,
        with the bound values included.
        In case of categorical dimensions the constraint enforces that only values specified in bounds can be drawn.

        Parameters
        ----------
        * `dimension` [int]:
            The index of the dimension for which constraint should be applied.

        * `bounds` [tuple]:
            The bounds for the constraint.
            For 'real' dimensions the tuple must be of length 2 and only consist of integers.

            For 'integer' dimensions the tuple must be of length 2 and only consist of floats.

            For 'categorical' dimensions the tuple must be of length < number of dimensions and lenght > 1.
                The tuple can contain any combination of str, int or float

        * `dimension_type` [str]:
            The type of dimension. Can be 'integer','real' or 'categorical.
            Should be the same type as the dimension it is applied to.
        """

        # We use another validation strategy for categorical dimensions.
        if dimension_type == 'categorical':
            self.validate_constraints = self._validate_constraint_categorical
        else:
            self.validate_constraints = self._validate_constraint_real

    def _validate_constraint_categorical(self, value):
        if value in self.bounds:
            return True
        else:
            return False

    def _validate_constraint_real(self, value):
        if value >= self.bounds[0] and value <= self.bounds[1]:
            return True
        else:
            return False

    def __repr__(self):
        return "Inclusive(dimension={}, bounds={}, space_Type={})".format(self.dimension, self.bounds, self.dimension_type)

    def __eq__(self, other):
        if isinstance(other, Inclusive):
            return all([a == b for a, b in zip(self.bounds, other.bounds)]) and self.dimension == other.dimension and self.dimension_type == other.dimension_type
        else:
            return False

class Exclusive(Bound_Constraint):
    def __init__(self, dimension, bounds, dimension_type):
        super().__init__(dimension, bounds, dimension_type) 
        """Constraint class of type Inclusive.

        This constraint enforces that all values drawn for the specified dimension are outside the bounds,
        with the bound values excluded.
        In case of categorical dimensions the constraint enforces that values specified in bounds can not be drawn.

        Parameters
        ----------
        * `dimension` [int]:
            The index of the dimension for which constraint should be applied.

        * `bounds` [tuple]:
            The bounds for the constraint.
            For 'real' dimensions the tuple must be of length 2 and only consist of integers.

            For 'integer' dimensions the tuple must be of length 2 and only consist of floats.

            For 'categorical' dimensions the tuple must be of length < number of dimensions and lenght > 1.
                The tuple can contain any combination of str, int or float

        * `dimension_type` [str]:
            The type of dimension. Can be 'integer','real' or 'categorical.
            Should be the same type as the dimension it is applied to.
        """

        # We use another validation strategy for categorical dimensions.
        if dimension_type == 'categorical':
            self.validate_constraints = self._validate_constraint_categorical
        else:
            self.validate_constraints = self._validate_constraint_real

    def _validate_constraint_categorical(self, value):
        if value in self.bounds:
            return False
        else:
            return True

    def _validate_constraint_real(self, value):
        if value >= self.bounds[0] and value <= self.bounds[1]:
            return False
        else:
            return True

    def __repr__(self):
        return "Exclusive(dimension={}, bounds={}, dimension_type={})".format(self.dimension, self.bounds, self.dimension_type)

    def __eq__(self, other):
        if isinstance(other, Exclusive):
            return all([a == b for a, b in zip(self.bounds, other.bounds)]) and self.dimension == other.dimension and self.dimension_type == other.dimension_type
        else:
            return False

def check_constraints(space,constraints):
    """ Checks if list of constraints is valid when compared with the dimensions of space.
        Throws errors otherwise

        Parameters
        ----------
        * `space` [Space]:
            A Space object.

        * `constraints` [list]:
            A list of constraint objects.
    """

    if not type(constraints) == list:
        raise TypeError('Constraints must be a list of constraints. Got {}'.format(type(constraints)))
    n_dims = space.n_dims

    single_constraints = [False]*n_dims
    for i in range(len(constraints)):
        constraint = constraints[i]
        ind_dim = constraint.dimension # Index of the dimension
        if not ind_dim < n_dims:
            raise IndexError('Dimension index {} out of range for n_dims = {}'.format(ind_dim,n_dims))
        space_dim = space.dimensions[constraint.dimension]

        # Check if space dimensions types are the same as constraint dimension types
        if isinstance(space_dim,Real):
            if not constraint.dimension_type == 'real':
                raise TypeError('Constraint for real dimension {} must be of dimension_type real. Got {}'.format(ind_dim,constraint.dimension_type))
        elif isinstance(space_dim,Integer):
            if not constraint.dimension_type == 'integer':
                raise TypeError('Constraint for integer dimension {} must be of dimension_type integer. Got {}'.format(ind_dim,constraint.dimension_type))
        elif isinstance(space_dim,Categorical):
            if not constraint.dimension_type == 'categorical':
                raise TypeError('Constraint for categorical dimension {} must be of dimension_type categorical. Got {}'.format(ind_dim,constraint.dimension_type))
        else:
            raise TypeError('Can not find valid dimension for' + str(space_dim))

        # Check if constraints are inside bounds of space and if more than one single constraint has been
        # applied to the same dimension
        if isinstance(constraint,Single):
            if single_constraints[ind_dim] == True:
                raise IndexError('Can not add more than one Singe-type constraint to dimension {}'.format(ind_dim))
            single_constraints[ind_dim] = True
            check_value(space_dim,constraint.value)
        elif isinstance(constraint,Inclusive) or isinstance(constraint,Exclusive):
            check_bounds(space_dim,constraint.bounds)
        else:
            raise TypeError('Constraints must be of type "Single", "Exlusive" or "Inclusive" ')

def check_bounds(dim,bounds):
    """ Checks if bounds are included in the dimension.
        Throws errors otherwise.

        Parameters
        ----------
        * `dim` [Dimension]:
            A Space object.

        * `bounds` [tuple]:
            A tuple of int, float or str depending on the type of dimension.
        """

    # Real or integer dimensions.
    if isinstance(dim,Real) or isinstance(dim,Integer):
        for value in bounds:
            if value < dim.low or value > dim.high:
                raise ValueError('Bounds {} exceeds bounds of space {}'.format(bounds,[dim.low,dim.high]))
    else: # Categorical dimensions.
        for value in bounds:
            if value not in dim.categories:
                raise ValueError('Categorical value {} is not in space with categories {}'.format(value,dim.categories))

def check_value(dim,value):
    """ Checks if value are included in the dimension.
        Throws errors otherwise.

        Parameters
        ----------
        * `dim` [Dimension]:
            A Space object.

        * `value` [int, float or str]:
            The type of `value` depends on the type of dimension.
        """

    # Real or integer dimension
    if isinstance(dim,Real) or isinstance(dim,Integer):
        if value < dim.low or value > dim.high:
            raise ValueError('Value {} exceeds bounds of space {}'.format(value,[dim.low,dim.high]))
    else: # Categorical dimension.
        if value not in dim.categories:
            raise ValueError('Categorical value {} is not in space with categoreis {}'.format(value,dim.categories))