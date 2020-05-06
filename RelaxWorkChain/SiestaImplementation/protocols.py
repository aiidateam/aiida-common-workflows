# -*- coding: utf-8 -*-
class ProtocolRegistry:
    """
    This class is meant to become the central engine for the management of protocols.
    With the word "protocol" we mean a series of suggested inputs for AiiDA
    WorkChains that allow users to more easly authomatize their workflows.
    Even though this approach could be general, at the moment I can only think
    about protocols in the context of DFT inputs (Siesta inputs in our case).
    The choice of the inputs of a DFT simulation should be carefully tested
    for any new system. Users must be aware of the limitations of using protocols,
    but, in theory, this platform could become the place where we collect
    the "know how" about Siesta inputs. We hope that, with time, more and more
    protocols might be added to cover in a robust way entire categories of materials.
    This is the very beginning of the development and, for the moment, only few
    methods and two very basic protocols are implemented. The two protocols
    are hard-coded here inside the class as private attributes, but surely
    in the future they will be moved outside (maybe external json files).
    Moreover the methods are just functions useful to retrieve information about
    protocols, but in the future we will probably need some kind of protocol algebra
    for merging, overriding, etc. protocol values.
    The management of the pseudos is, in particular, very fragile. It imposes that the user
    loads a pseudo_family with the exact same name of the one hard-coded for the
    protocol.
    """

    _protocol_registy = {
        'standard': {
            'description': 'A standard list of inputs for Siesta. Never tested! Proof of concept at the moment.',
            'parameters': {
                'max-scfiterations': 50,
                'dm-numberpulay': 4,
                'dm-mixingweight': 0.3,
                'dm-tolerance': 1.e-3,
                'solution-method': 'diagon',
                'electronic-temperature': '25 meV',
                'write-forces': True,
                'min_meshcut': 80
            },
            'atomic_heuristics': {
                'H': {
                    'cutoff': 100
                },
                'Si': {
                    'cutoff': 101
                }
            },
            'basis': {
                'pao-energy-shift': '100 meV',
                'pao-basis-size': 'DZ'
            },
            'kpoints': {
                'distance': 0.3,
                'offset': [0., 0., 0.]
            },
            'pseudo_family': 'nc-fr-04_pbe_standard_psml',
            'threshold_forces': 0.04,  #in ev/ang
            'threshold_stress': 0.006241509125883258,  #in ev/ang**3 = 1 GPa
        },
        'stringent': {
            'description': 'Another test set.',
            'parameters': {
                'max-scfiterations': 50,
                'dm-numberpulay': 4,
                'dm-mixingweight': 0.3,
                'dm-tolerance': 1.e-4,
                'solution-method': 'diagon',
                'electronic-temperature': '25 meV',
                'write-forces': True,
                'min_meshcut': 100
            },
            'atomic_heuristics': {
                'H': {
                    'cutoff': 101
                },
                'Si': {
                    'cutoff': 103
                }
            },
            'basis': {
                'pao-energy-shift': '100 meV',
                'pao-basis-size': 'DZP'
            },
            'kpoints': {
                'distance': 0.2,
                'offset': [0., 0., 0.]
            },
            'pseudo_family': 'nc-fr-04_pbe_stringent_psml',
            'threshold_forces': 0.03,  #in ev/ang
            'threshold_stress': 0.005,  #in ev/ang**3
        },
    }

    @classmethod
    def get_protocol_names(cls):
        return cls._protocol_registy.keys()

    @classmethod
    def get_default_protocol_name(cls):
        return 'standard'

    @classmethod
    def get_protocol_info(cls, key):
        if key in cls._protocol_registy:
            return cls._protocol_registy[key]['description']
        else:
            raise ValueError('Wrong protocol: no protocol with name {} implemented'.format(key))

    #This maybe should become private!
    @classmethod
    def get_protocol(cls, key):
        if key in cls._protocol_registy:
            return cls._protocol_registy[key]
        else:
            raise ValueError('Wrong protocol: no protocol with name {} implemented'.format(key))

    @classmethod
    def is_pseudofamily_loaded(cls, key):
        from aiida.common import exceptions
        from aiida.orm.groups import Group
        if key in cls._protocol_registy:
            try:
                famname = cls._protocol_registy[key]['pseudo_family']
                Group.get(label=famname)
            except:
                raise exceptions.NotExistent(
                    'You selected protocol {}, but the corresponding '
                    'pseudo_family is not loaded. Please download {} from PseudoDojo and create '
                    'a pseudo_family with the same name'.format(key, famname)
                )
        else:
            raise ValueError('Wrong protocol: no protocol with name {} implemented'.format(key))
