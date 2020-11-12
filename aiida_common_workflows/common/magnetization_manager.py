# -*- coding: utf-8 -*-
"""
Utilities to manage initial magnetization.
"""
from aiida.orm import StructureData


class InitMagnetizationManager():
    """
    A manager to facilitate the management of initial magnetizations.
    The API agreed in the project impose to pass the initial magnetizations
    as a list with the spin polarization (difference between spin up and down electrons)
    for each site.
    The manager requires in input for the initaialization this list and the structure
    and contains methods to manage these quantities.
    """

    def __init__(self, structure, magnetization_per_site):
        """
        Construct an instance of InitMagnetizationManager
        :param: structure: a StructureData
        :param: initial_spin_site: a list with the spin polarization per site.
                The values are the difference between the up-spin electrons and
                down-spin electrons in the site. The order of the list follows the
                one of the structure.sites
        """

        if not isinstance(structure, StructureData):
            raise ValueError('structure input must be a StructureData')

        if not isinstance(magnetization_per_site, list):
            raise ValueError('magnetization_per_site must be a list')

        if len(magnetization_per_site) != len(structure.sites):
            raise ValueError('an initial magnetization for each site must be spedified')

        self.structure = structure
        self.magnetization_per_site = magnetization_per_site

    def get_per_site_list(self):
        """
        Return the list of spin polarization per site.
        """
        return self.magnetization_per_site

    def get_per_kind_dict_and_structure(self):
        """
        Return a dictionary containing a mapping between the kinds and the initial
        magnetizaton.
        In case two (or more) sites with same kind have different initial magnetizations
        a new structure is created to support this situation.
        :return: The dictionary mapping kind with initial polarization
                 The StructureData with modified kinds able to accomodate the
                   initial magnetization passed by the user.
        """

        def set_new_kind(site):
            """
            Ausiliary function assigning to a site a new kind.
            It selects automatically the name of the new kind as the old kind name
            of the site plus an integer.
            :param: site. The site index for the site that will change kind.
            :return: the name of the new kind assigned to site.
            """
            old_kind_name = new_structure.attributes['sites'][site]['kind_name']
            number = 1
            #Check if there is a previously modified site with a number assigned.
            #This is discovered looking at sites containing the "old_kind_name" but
            #that were not in the original structure.
            for i in new_structure.sites:
                if old_kind_name in i.kind_name:
                    if i.kind_name not in [kind.name for kind in self.structure.kinds]:
                        #The remaining part must be a number
                        number = int(i.kind_name.replace(old_kind_name, ''))
            new_kind_name = old_kind_name + '{}'.format(number + 1)
            new_structure.attributes['sites'][site]['kind_name'] = new_kind_name
            additional_kind = new_structure.get_kind(old_kind_name)
            additional_kind.name = new_kind_name
            new_structure.append_kind(additional_kind)
            return new_kind_name

        def modify_site_kind(site, coll_magn_index):
            """
            Ausiliary function that modifies the kind of a site. It sets a kind
            that was previously created with `set_new_kind`.
            :param: site. The site index for the site that will change kind.
            :param: coll_magn_index. An index from which extract the correct kind to assigne to site.
            """
            old_kind_name = new_structure.attributes['sites'][site]['kind_name']
            number = coll_magn_index + 1
            new_kind_name = old_kind_name + '{}'.format(number)
            new_structure.attributes['sites'][site]['kind_name'] = new_kind_name

        dict_kinds = {}
        collect_magn = {}
        new_structure = self.structure.clone()

        for index in range(len(self.structure.sites)):
            kind = self.structure.sites[index].kind_name
            magn = self.magnetization_per_site[index]
            if kind not in dict_kinds:
                dict_kinds[kind] = magn
                collect_magn[kind] = [magn]
            else:
                if magn not in collect_magn[kind]:
                    collect_magn[kind].append(magn)
                    print('need to define a new kind!')
                    new_kind = set_new_kind(index)
                    dict_kinds[new_kind] = magn
                else:
                    #We need to check if the kind of the site needs to be modified
                    coll_magn_index = collect_magn[kind].index(magn)
                    if coll_magn_index != 0:
                        modify_site_kind(index, coll_magn_index)

        return dict_kinds, new_structure
