import os, sys, inspect
import re
import numpy as np
from VirgoDataLoader import VirgoDataLoader

# For TrickPy, the python module that can load trick data record produced files
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, 'deps')))

class VirgoTrickpyFileLoader(VirgoDataLoader):
    """
    Class that manages loading data from the scene data_source: trickpy: section
    of a dict in Virgo-expected format

    Uses trickpy to load the data, then puts it into a format best suited
    for consumption in the Virgo framework
    """
    def __init__(self, run_dir, trickpy_dict, verbosity=1):
        super().__init__()
        self.run_dir=run_dir
        self.trickpy_dict=dict(trickpy_dict)
        self.verbosity=verbosity
        self.drg = None

    @staticmethod
    def expand_arrays(varname):
        """
        Given a string, check the string for array syntax ([ - ]). If the given variable
        specifies an array, return the string expanded into a list containing each array
        member.

        For consistency's sake, a list is always returned, even when the given string
        is not expanded.

        For example:
        input: varname="path.to.variable[0-2]"
        output: ["path.to.variable[0]", "path.to.variable[1]", "path.to.variable[2]"]

        input: "variable"
        output: ["variable"]

        Args:
            varname (string): A string containing the trick name corresponding to the
            given alias.
        """
        # Define a regex which finds any text that uses our format for
        # multiple elements in an array: ([ - ]).
        array_regex = re.compile(r"(?<=\[)\w+(?:-\w+)+(?=\])")
        new_varname = [varname]
        found_match = True
        while found_match:
            found_match = False
            for i, s in enumerate(new_varname):
                match = array_regex.search(s)
                if match:
                    if "-" in match.group():
                        found_match = True
                        start_index = int(match.group().split("-")[0])
                        stop_index = int(match.group().split("-")[1])
                        # Replace trick-name with list of each array element:
                        new_varname[i : i + 1] = [s[: match.start()] + str(ii) + s[match.end() :] for ii in range(start_index, stop_index + 1)]
                    else:
                        print("Regex expression error.")
        return new_varname

    def load_variables(self):
        """
        Use trickpy to load the variables defined in the 'trickpy:' section
        of the scene. The way trickpy's load_run function currently works is like
        this:

          self.drg = dr.load_run(self.run_dir, variables=load_these_variables)

        Where variables is a list of all variables to load regardless of group. Meaning
        if two groups both specify variable pos[0-2], self.drg will have both of them
        listed separated by groups (key in the dict). Furthermore, duplicate entries
        in the variables list argument are not harmful, nor is there any error produced
        by TrickPy if a listed variable is not found.

        Populates: self.drg
        Returns:   self.drg
        Raises: RuntimeError if a 'var' in 'trickpy:' is not found when loading
        the self.run data, or if other errors occur

        TODO: Need uniqueness check, no group/var combo should be repeated twice
              in the trickpy: area
        TODO: need more error checking here, if trickpy:: section has bad variables
              we can error on the expected_vars.remove() line
        """
        import trickpy.data_record as dr
        load_these_variables = []
        expected_groups = []
        for alias in self.trickpy_dict:
          if 'group' in self.trickpy_dict[alias]:
            expected_groups.append(self.trickpy_dict[alias]['group'])
        expected_groups = list(set(expected_groups))
        # Find every var: given in the scene dict and pass them to dr.load_run
        # as the subset of variables to load.
        for v in self.trickpy_dict:
          expanded_vars = self.expand_arrays(self.trickpy_dict[v]['var'])
          load_these_variables += expanded_vars
        if len(load_these_variables) == 0:
          msg = (f"ERROR: There are no variables in the trickpy:: section of scene. "
                f"Nothing to load! ")
          raise RuntimeError (msg)
        # Remove any duplicate entries
        load_these_variables = list(set(load_these_variables))

        if self.verbosity > 0:
            print(f"Loading data from {self.run_dir}...")
            if self.verbosity > 1:
                for v in load_these_variables:
                    print(f"  {v}")

        # We skip_errors=True to ignore the known issue where a CSV file of 0 bytes
        # will raise an error in _read_csv_info:703 -Jordan 5/2026
        self.drg = dr.load_run(self.run_dir, variables=load_these_variables,
                               skip_errors=True)
        if self.verbosity > 0:
            print(f"Done.")

        # Make sure dr.load_run found all the vars we requested since 
        # trickpy doesn't error if some were not found
        expected_vars = list(load_these_variables)
        for group in self.drg:
          if group not in expected_groups:
            continue
          if len(expected_vars) == 0:
             break
          for var in self.drg[group]:
            if len(expected_vars) == 0:
               break
            if var in expected_vars:
              expected_vars.remove(var)
              continue
        if len(expected_vars) > 0:
          msg = (f"ERROR: The following variables from trickpy: section of scene "
                f"were not found in data loading of {self.run_dir}\n"
                f"{sorted(expected_vars)}")
          raise RuntimeError (msg)
        return (self.drg)

    def does_alias_exist(self, alias):
      """
      TODO: can this handle if [] are in the alias? I don't think so
      """
      (alias, indices) = self.split_alias_and_indices(alias_in=alias)
      if alias in self.trickpy_dict:
        variable = self.trickpy_dict[alias]['var']
        return(self.does_variable_exist(variable))
      else:
        return False

    @staticmethod
    def split_alias_and_indices(alias_in):
        """
        Search for the [] specified_indices in the alias given, and split it
        into alias=(alias with no specified_indices),
        specified_indices=(specified_indices) where specified_indices is None
        if not given
        """
        alias=str(alias_in)
        specified_indices = ''
        indices_pattern = r"\[.*\]"
        match = re.search(indices_pattern, alias)
        if match:
            specified_indices = match.group(0)
            alias = alias.split(specified_indices)[0]
        return (alias, specified_indices)

    def does_variable_exist(self, variable):
        """
        Query self.drg for the existence of variable
        """
        exists = False
        for grp in self.drg:
          expanded_variables = self.expand_arrays(variable)
          #import pdb; pdb.set_trace()
          for var in expanded_variables:
              # TODO this is a loose check, it doesn't check for all array indices
              if var in self.drg[grp]:
                exists = True
                break
        return exists

    def get_alias_data(self, alias):
        """
        Get the values associated with a single variable alias defined in
        trickpy:: dict. For example, for this YAML equivalent of a dict:

        trickpy::
          time:                          # Variable Alias
            group: Satellite             # DR Group  
            var: sys.exec.out.time       # DR variable name
          sat_pos:                       # Variable Alias
            group: Satellite             # DR Group
            var: dyn.satellite.pos[0-2]  # DR variable name
          sat_vel:                       # Variable Alias
            group: Satellite             # DR Group
            var: dyn.satellite.vel[0-2]  # DR variable name

        For variables with index ranges ([0-2] or [0-2][0-2] for example) the
        indices must be specified such that a single variable is requested.

        For example get_alias_data(alias='sat_pos[0]') will return a list of 
        dyn.satellite.pos[0] values associated with group Satellite.

        Returns: A list of data values associated with alias

        Raises: RuntimeError if unable to find data associated with alias or there's
          an issue with the indices specified.
        """
        import re
        if not self.drg:
          msg = (f"ERROR: Cannot get_alias_data as self.drg is not populated.")
          raise RuntimeError (msg)

        alias, specified_indices = self.split_alias_and_indices(alias)
        if alias not in self.trickpy_dict:
          msg = (f"ERROR: {alias} not found in trickpy: section of scene. Make sure to use"
                 " the alias name, not the var: name.")
          raise RuntimeError (msg)

        variable = self.trickpy_dict[alias]['var']
        #print(f"DEBUG BEFORE variable: {variable} and alias: {alias}")
        var_indices = ''
        # Search for the [] var_indices in the var associated with the alias
        # given, and split it into variable=(variable with no var_indices),
        # var_indices=(var_indices) where var_indices is None if not given
        variable, var_indices = self.split_variable_indices(variable)
        #print(f"DEBUG MID: variable:{variable}  var_indices:{var_indices}   specified_indices: {specified_indices}")
        # TODO: This check may not be robust to two-dimensional arrays, if alias=rot[0] for
        # example but the underlying var is defined as rotation[0-2][0-2]
        if specified_indices == '':
          if '-' in var_indices:
            msg = (f"ERROR: {alias} is multidimensional. Specify indices to request a single " 
                   "variable instead, ex: pos[0] instead of pos, rot[1][2] instead of rot")
            raise RuntimeError (msg)
          # If we got here that means the alias refers to a single array value
          # so it's safe to assign specified_indices directly to var_indices
          specified_indices = var_indices
        grp = self.trickpy_dict[alias]['group']
        #print(f"DEBUG END: variable:{variable}  var_indices:{var_indices} group: {grp}  specified_indices: {specified_indices}")
        return self.drg[grp][variable+specified_indices].tolist()
        
    @staticmethod
    def split_variable_indices(s):
        """
        A function designed to split off the last occurance of a variable
        indices pattern, returning the string leading up to that indices
        pattern and the indices matched to that pattern. Here are several
        examples of the form  (input  ->  first match | second match)

        sys.exec.out.time                   -> "sys.exec.out.time" | ""
        time                                -> "time" | ""
        position[0]                         -> "position" | "[0]"
        position[0-2]                       -> "position" | "[0-2]"
        my.foo[0].position[0-2]             -> "my.foo[0].position" | "[0-2]"
        my.foo[0].position[0]               -> "my.foo[0].position" | "[0]"
        my.foo[0].R[0-2][0-2]               -> "my.foo[0].R" | "[0-2][0-2]"
        my.foo[0].bar[0]                    -> "my.foo[0].bar" | "[0]"
        my.foo[0].opacity                   -> "my.foo[0].opacity" | ""
        my.foo[0][1].bar[0][0]              -> "my.foo[0][1].bar" | "[0][0]"
        my.foo[0][1].bar[0-2][0-2]          -> "my.foo[0][1].bar" | "[0-2][0-2]"
        my.foo[0][0][0].hello               -> "my.foo[0][0][0].hello" | ""
        my.foo[0][0][0].hi[0]               -> "my.foo[0][0][0].hi" | "[0]"
        my.foo[0][0][0].hi[0][2]            -> "my.foo[0][0][0].hi" | "[0][2]"
        my.foo[0][0][0].hi[0-2][0-2]        -> "my.foo[0][0][0].hi" | "[0-2][0-2]"
        """
        # Match: (anything)(one or more bracket pairs at the end)
        # Bracket pairs can contain digits and hyphens: [0], [0-2], etc.
        match = re.match(r'^(.+?)((?:\[[\d\-]+\])+)$', s)
        if match:
            return match.group(1), match.group(2)
        else:
            # No indices at the end
            return s, ''

    def get_alias_datas(self, alias):
        """
        Get datas (more than one value at a time) associated with an
        alias defined in trickpy: dict. For example, for this YAML
        equivalent of a dict:

        trickpy::
          time:                          # Variable Alias
            group: Satellite             # DR Group  
            var: sys.exec.out.time       # DR variable name
          sat_pos:                       # Variable Alias
            group: Satellite             # DR Group
            var: dyn.satellite.pos[0-2]  # DR variable name
          sat_vel:                       # Variable Alias
            group: Satellite             # DR Group
            var: dyn.satellite.vel[0-2]  # DR variable name

        This function returns entire sets of recorded data as lists of primitives
        arranged by array sizes of the data. For example:
           No array  (ex: time)      Returns a list of time values
           1-D array (ex sat_pos)    Returns a list of tuples where is tuple is of size
                                     associated with the 1-D array, e.g.
                                     [(x0, y0, z0), (x1, y1, z1) ... ]
           2-D array (ex sat_rot)    Returns a list of np.arrays of size associated with
                                     the 2-D array, e.g.
                                     [ 
                                       np.array((R0[0][0], R0[0][1], R0[0][2]),
                                                (R0[1][0], R0[1][1], R0[1][2]),
                                                (R0[2][0], R0[2][1], R0[2][2])),
                                       np.array((R1[0][0], R1[0][1], R1[0][2]),
                                                (R1[1][0], R1[1][1], R1[1][2]),
                                                (R1[2][0], R1[2][1], R1[2][2])),
                                       ...

                                       ]

        Returns: A list of lists of data values associated with alias, as acquired
         from the trickpy module

        Raises: RuntimeError if unable to find data associated with alias or there's
          an issue with the indices specified.
        """
        datas = []
        # This function doesn't want indices, if we detect them, error out
        alias, alias_indices = self.split_variable_indices(alias)
        if alias_indices != '':
            msg = (f"ERROR: Indices found in {alias}. Do not include indices [] when calling "
                   "get_alias_datas()")
            raise RuntimeError (msg)
        # Get the array indices defintion from the variable in the scene
        grp = self.trickpy_dict[alias]['group']
        variable = self.trickpy_dict[alias]['var']

        # Expand the variables to see how many array indices there are
        expanded_variables = self.expand_arrays(variable)
        if len(expanded_variables) == 1:
            datas = self.drg[grp][expanded_variables[0]].tolist()
        elif len(expanded_variables) == 3:
            datas = list(zip(
                self.drg[grp][expanded_variables[0]].tolist(),
                self.drg[grp][expanded_variables[1]].tolist(),
                self.drg[grp][expanded_variables[2]].tolist()))
        elif len(expanded_variables) == 9:
            list_length = len(self.drg[grp][expanded_variables[0]])
            for i in range(0, list_length):
                datas.append( np.array(
                [  [ self.drg[grp][expanded_variables[0]][i], self.drg[grp][expanded_variables[1]][i], self.drg[grp][expanded_variables[2]][i] ],
                   [ self.drg[grp][expanded_variables[3]][i], self.drg[grp][expanded_variables[4]][i], self.drg[grp][expanded_variables[5]][i] ],
                   [ self.drg[grp][expanded_variables[6]][i], self.drg[grp][expanded_variables[7]][i], self.drg[grp][expanded_variables[8]][i] ] ] )
                ) 

        return datas
