#!/usr/bin/env python
# encoding: utf-8


from __future__ import print_function, division
# Python stdlib
import Tkinter as tk
import Pmw
from multiprocessing import cpu_count
from random import choice
from string import ascii_letters
# Chimera stuff
import chimera
import chimera.tkgui
from chimera import UserError
from chimera.baseDialog import ModelessDialog
from chimera.widgets import MoleculeScrolledListBox, SortableTable, MoleculeOptionMenu
# Own
from libplume.ui import PlumeBaseDialog, STYLES
from core import Controller, Model
from pygaussian import (MM_FORCEFIELDS, MEM_UNITS, JOB_TYPES, QM_METHODS, QM_FUNCTIONALS,
                        QM_BASIS_SETS, QM_BASIS_SETS_EXT)



def showUI(callback=None, *args, **kwargs):
    if chimera.nogui:
        tk.Tk().withdraw()
    ui = CauchianDialog(*args, **kwargs)
    model = Model(gui=ui)
    controller = Controller(gui=ui, model=model)
    ui.enter()
    if callback:
        ui.addCallback(callback)


class CauchianDialog(PlumeBaseDialog):

    buttons = ('Preview', 'Copy', 'Export', 'Import', 'Close')
    statusResizing = False
    default = 'Preview'

    def __init__(self, *args, **kwargs):
        # GUI init
        self.title = 'Plume Cauchian'

        # Molecule variables
        self.var_molecule_replicas = tk.IntVar()

        # Job variables
        self.var_job = tk.StringVar()
        self.var_job_options = tk.StringVar()
        self.var_frequencies = tk.IntVar()
        self.var_connectivity = tk.IntVar()
        self.var_calculation = tk.StringVar()
        self.var_solvent = tk.StringVar()

        # QM variables
        self.var_qm_method = tk.StringVar()
        self.var_qm_functional = tk.StringVar()
        self.var_qm_functional_type = tk.StringVar()
        self.var_qm_basis_kind = tk.StringVar()
        self.var_qm_basis_ext = tk.StringVar()
        self.var_qm_basis_set = tk.StringVar()
        self._qm_basis_extra = {}
        self.var_qm_keywords = tk.StringVar()

        # MM variables
        self._layers = {}
        self.var_mm_forcefield = tk.StringVar()
        self.var_mm_water_forcefield = tk.StringVar()
        self.var_mm_frcmod = tk.StringVar()

        # Charges & Multiplicity
        self.var_charge_qm = tk.IntVar()
        self.var_charge_mm = tk.IntVar()
        self.var_multiplicity_qm = tk.IntVar()
        self.var_multiplicity_mm = tk.IntVar()

        # Flexibility & restraints
        self._restraints = {}

        # Hardware & Output variables
        self.var_title = tk.StringVar()
        self.var_title.set('Untitled Job')
        self.var_checkpoint = tk.IntVar()
        self.var_checkpoint_path = tk.StringVar()
        self.var_nproc = tk.IntVar()
        self.var_memory = tk.IntVar()
        self.var_memory_units = tk.StringVar()

        # Misc
        self._basis_set_dialog = None
        self.ui_labels = {}

        # Fire up
        super(CauchianDialog, self).__init__(*args, **kwargs)

    def fill_in_ui(self, parent):
        # Select molecules
        self.ui_molecule_frame = tk.LabelFrame(self.canvas, text='Select molecules')
        self.ui_molecules = MoleculeScrolledListBox(self.ui_molecule_frame)
        self.ui_molecules_replicas = MoleculeScrolledListBox(self.ui_molecule_frame)
        self.ui_molecules_replica_chk = tk.Checkbutton(self.canvas, text='With replicas',
                                                         variable=self.var_molecule_replicas)

        self.ui_molecule_frame.columnconfigure(0, weight=3)
        self.ui_molecule_frame.columnconfigure(1, weight=1)
        self.ui_molecule_frame.rowconfigure(1, weight=1)
        mol_options = {'padx': 5, 'pady': 5}
        self.ui_molecules.grid(in_=self.ui_molecule_frame, row=0, column=0,
                rowspan=2, sticky='news', **mol_options)
        self.ui_molecules_replica_chk.grid(in_=self.ui_molecule_frame, row=0, column=1,
                sticky='we', **mol_options)
        self.ui_molecules_replicas.grid(in_=self.ui_molecule_frame, row=1, column=1,
                sticky='news', **mol_options)

        # Modelization
        self.ui_model_frame = tk.LabelFrame(self.canvas, text='Modelization')
        self.ui_job = Pmw.OptionMenu(self.canvas, items=JOB_TYPES, initialitem=0,
                                     menubutton_textvariable=self.var_job)
        self.ui_job_options = Pmw.ComboBox(self.canvas, entry_textvariable=self.var_job_options,
                                           history=True, unique=True, dropdown=True)
        self.ui_frequencies = tk.Checkbutton(self.canvas, variable=self.var_frequencies,
                                             text='+ Freq')
        self.ui_connectivity = tk.Checkbutton(self.canvas, variable=self.var_connectivity,
                                             text='With connectivity')
        self.ui_calculation = Pmw.OptionMenu(self.canvas, items=['QM', 'ONIOM'], initialitem=0,
                                             menubutton_textvariable=self.var_calculation)
        self.ui_layers = tk.Button(self.canvas, text='Define layers')
        self.ui_solvent = Pmw.OptionMenu(self.canvas, items=['Implicit', 'Explicit'], initialitem=0,
                                         menubutton_textvariable=self.var_solvent,
                                         hull_width=10)
        self.ui_solvent_cfg = tk.Button(self.canvas, text='Configure', state='disabled')
        self.ui_redundant_btn = tk.Button(self.canvas, text='Edit redundant coordinates',
                                          state='disabled')

        model_grid = [['Model', self.ui_calculation, self.ui_layers],
                      ['Job', self.ui_job, self.ui_job_options],
                      [self.ui_frequencies, self.ui_connectivity, self.ui_redundant_btn],
                      ['Solvent', self.ui_solvent, self.ui_solvent_cfg]]
        self.auto_grid(self.ui_model_frame, model_grid, padx=3, pady=3)

        # QM configuration
        self.ui_qm_frame = tk.LabelFrame(self.canvas, text='QM Settings')
        self.ui_qm_methods = Pmw.OptionMenu(self.canvas, items=QM_METHODS, initialitem=6,
                                            menubutton_textvariable=self.var_qm_method)
        self.ui_qm_functional_type = Pmw.OptionMenu(self.canvas, initialitem=0,
                                                    items=sorted(QM_FUNCTIONALS.keys()),
                                                    menubutton_textvariable=self.var_qm_functional_type)
        self.ui_qm_functionals = Pmw.OptionMenu(self.canvas, initialitem=0,
                                                items=QM_FUNCTIONALS['Pure'],
                                                menubutton_textvariable=self.var_qm_functional)
        self.ui_qm_basis_kind = Pmw.OptionMenu(self.canvas, items=QM_BASIS_SETS, initialitem=0,
                                          menubutton_textvariable=self.var_qm_basis_kind)
        self.ui_qm_basis_ext = Pmw.OptionMenu(self.canvas, items=QM_BASIS_SETS_EXT, initialitem=0,
                                              menubutton_textvariable=self.var_qm_basis_ext)
        self.ui_qm_basis_per_atom = tk.Button(self.canvas, text='Per-element')
        self.ui_qm_basis_custom_set = tk.Entry(self.canvas, textvariable=self.var_qm_basis_set)
        self.ui_qm_keywords = Pmw.ComboBox(self.canvas, entry_textvariable=self.var_qm_keywords,
                                           history=True, unique=True, dropdown=True)

        qm_grid = [['Method', (self.ui_qm_methods, 'Functional', self.ui_qm_functional_type, self.ui_qm_functionals)],
                   ['Basis set', (self.ui_qm_basis_kind, self.ui_qm_basis_ext, self.ui_qm_basis_custom_set, self.ui_qm_basis_per_atom)],
                   ['Extra keywords', self.ui_qm_keywords]]
        self.auto_grid(self.ui_qm_frame, qm_grid)

        # MM Configuration
        self.ui_mm_frame = tk.LabelFrame(self.canvas, text='MM Settings')
        self.ui_mm_forcefields = Pmw.OptionMenu(self.canvas, initialitem=0,
                                                items=MM_FORCEFIELDS['General'],
                                                menubutton_textvariable=self.var_mm_forcefield)
        self.ui_mm_water_forcefield = Pmw.OptionMenu(self.canvas, initialitem=0,
                                                items=MM_FORCEFIELDS['Water'],
                                                menubutton_textvariable=self.var_mm_water_forcefield)
        self.ui_mm_frcmod = tk.Entry(self.canvas, textvariable=self.var_mm_frcmod)
        self.ui_mm_frcmod_btn = tk.Button(self.canvas, text='...')

        mm_grid = [['Forcefield', self.ui_mm_forcefields],
                   ['Waters', self.ui_mm_water_forcefield],
                   ['Frcmod', (self.ui_mm_frcmod, self.ui_mm_frcmod_btn)]]
        self.auto_grid(self.ui_mm_frame, mm_grid)

        # Charges & multiplicity
        self.ui_charges_frame = tk.LabelFrame(self.canvas, text='Charges & Multiplicity')
        self.ui_charges_auto = tk.Button(self.canvas, text='Automatic', state='disabled')
        self.ui_charges_manual = tk.Button(self.canvas, text='Manual', state='disabled')
        self.ui_charges_qm = tk.Entry(self.canvas, textvariable=self.var_charge_qm, width=5)
        self.ui_charges_mm = tk.Entry(self.canvas, textvariable=self.var_charge_mm, width=5)
        self.ui_multiplicity_qm = tk.Entry(self.canvas, textvariable=self.var_multiplicity_qm, width=5)
        self.ui_multiplicity_mm = tk.Entry(self.canvas, textvariable=self.var_multiplicity_mm, width=5)

        charges_grid = [['Set charges:', self.ui_charges_auto, self.ui_charges_manual],
                        ['Total charge:', (self.ui_charges_qm, '(QM)'), (self.ui_charges_mm, '(MM)')],
                        ['Multiplicity:', (self.ui_multiplicity_qm, '(QM)'), (self.ui_multiplicity_mm, '(MM)')]]
        self.auto_grid(self.ui_charges_frame, charges_grid, resize_columns=(1,2), label_sep='')

        # Hardware
        self.ui_hw_frame = tk.LabelFrame(self.canvas, text='Output')
        self.ui_title = tk.Entry(self.canvas, textvariable=self.var_title)
        self.ui_title_btn = tk.Button(self.canvas, text='Random',
            command=lambda:self.var_title.set(''.join(choice(ascii_letters) for i in range(8))))
        self.ui_checkpoint = tk.Checkbutton(self.canvas, variable=self.var_checkpoint, text='Check:')
        self.ui_checkpoint_fld = tk.Entry(self.canvas, textvariable=self.var_checkpoint_path)
        self.ui_checkpoint_btn = tk.Button(self.canvas, text='Browse')
        self.ui_nproc = tk.Entry(self.canvas, textvariable=self.var_nproc, width=5)
        self.ui_nproc_btn = tk.Button(self.canvas, text='Get',
            command=lambda:self.var_nproc.set(cpu_count()))
        self.ui_memory = tk.Entry(self.canvas, textvariable=self.var_memory, width=5)
        self.ui_memory_units = Pmw.OptionMenu(self.canvas, items=MEM_UNITS, initialitem=2,
                                              menubutton_textvariable=self.var_memory_units)
        hw_grid = [['Job title', self.ui_title, self.ui_title_btn, '# CPUs', self.ui_nproc, self.ui_nproc_btn],
                   [self.ui_checkpoint, self.ui_checkpoint_fld, self.ui_checkpoint_btn, 'Memory', self.ui_memory, self.ui_memory_units]]
        self.auto_grid(self.ui_hw_frame, hw_grid, sticky='news')

        # Live output
        self.ui_preview_frame = tk.LabelFrame(self.canvas, text='Preview output')
        self.ui_preview = Pmw.ScrolledText(self.canvas, text_state='disabled',
                                           text_padx=4, text_pady=4, usehullsize=True,
                                           hull_width=300, hull_height=200,
                                           text_font='Monospace')
        self.ui_preview.pack(in_=self.ui_preview_frame, expand=True, fill='both', padx=5, pady=5)

        self.ui_molecule_frame.grid(row=0, column=0, sticky='news', padx=5, pady=5)
        self.ui_qm_frame.grid(row=0, column=1, columnspan=2, sticky='news', padx=5, pady=5)
        self.ui_model_frame.grid(row=1, column=0, sticky='news', padx=5, pady=5)
        self.ui_mm_frame.grid(row=1, column=1, sticky='news', padx=5, pady=5)
        self.ui_charges_frame.grid(row=1, column=2, sticky='news', padx=5, pady=5)
        self.ui_hw_frame.grid(row=2, columnspan=3, sticky='ew', padx=5, pady=5)
        self.canvas.columnconfigure(0, weight=1)
        self.canvas.columnconfigure(1, weight=1)
        self.canvas.columnconfigure(2, weight=1)
        self.canvas.rowconfigure(100, weight=1)
        self.ui_preview_frame.grid(row=100, columnspan=3, sticky='news', padx=5, pady=5)

    def Export(self):
        pass

    def Import(self):
        pass

    def Preview(self):
        pass

    def Copy(self):
        pass


###############################################
#
# CustomBasisSet Dialog
#
###############################################
ELEMENTS = [
    ["H",  "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",    "",    "",   "",    "He" ],
    ["Li", "Be", "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "B",  "C",   "N",   "O",  "F",   "Ne" ],
    ["Na", "Mg", "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "Al", "Si",  "P",   "S",  "Cl",  "Ar" ],
    ["K",  "Ca", "Sc", "Ti", "V",  "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga",  "Ge", "As",  "Se", "Br",  "Kr" ],
    ["Rb", "Sr", "Y",  "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In",  "Sn", "Sb",  "Te", "I",   "Xe" ],
    ["Cs", "Ba", "",   "Hf", "Ta", "W",  "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl",  "Pb", "Bi",  "Po", "At",  "Rn" ],
    ["Fr", "Ra", "",   "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Uut", "Fl", "Uup", "Lv", "Uus", "Uuo"],
    ["",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",    "",    "",   "",    ""   ],
    ["",   "",   "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho",  "Er", "Tm",  "Yb", "Lu",  ""   ],
    ["",   "",   "Ac", "Th", "Pa", "U",  "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es",  "Fm", "Md",  "No", "Lr",  ""   ]]
ALL_ELEMENTS = [element for row in ELEMENTS for element in row if element]


class BasisSetDialog(PlumeBaseDialog):

    """
    A Tkinter GUI to EMSL Basis Set Exchange database. Requires ebsel
    as an API to local dumps of BSE.
    """

    buttons = ('Copy', 'OK', 'Close')

    def __init__(self, saved_basis, *args, **kwargs):
        try:
            from ebsel.EMSL_local import EMSL_local
        except ImportError:
            raise chimera.UserError('Package ebsel not found. Please, install it first from:\n'
                                    'https://github.com/jaimergp/ebsel')
        # GUI init
        self.title = 'BasisSet Database'
        self._saved_basis = saved_basis
        self.saved_basis = saved_basis.copy()

        # Variables
        self.var_elements = {e: tk.IntVar() for e in ALL_ELEMENTS}
        # Constants
        self.db = EMSL_local(fmt="g94")
        self.db_basissets = sorted([b for (b, d) in self.db.get_available_basis_sets()])

        # Fire up
        super(BasisSetDialog, self).__init__(*args, **kwargs)

    def OK(self):
        self._saved_basis.clear()
        self._saved_basis.update(self.saved_basis)
        self.Close()

    def fill_in_ui(self, parent):
        self.canvas.columnconfigure(1, weight=1)
        self.ui_basis_set_frame = tk.LabelFrame(self.canvas, text='Choose a basis set')
        self.ui_basis_set_frame.grid(rowspan=2, row=0, column=0, sticky='news', pady=5, padx=5)
        self.ui_basis_sets = Pmw.ScrolledListBox(self.ui_basis_set_frame,
                                                 items=self.db_basissets,
                                                 selectioncommand=self._cb_basissets_changed)
        self.ui_basis_sets.pack(fill='y', expand=True, padx=2, pady=5)
        self.ui_basis_set_restore = tk.Button(self.ui_basis_set_frame, text='Reset all',
                                              command=self._reset_all)
        self.ui_basis_set_restore.pack(fill='x', padx=2, pady=5)

        self.ui_periodic_table = tk.LabelFrame(self.canvas, text='Choose elements')
        self.ui_periodic_table.grid(row=0, column=1, columnspan=5, sticky='news', pady=5, padx=5)
        self.ui_elements = {}
        for i, row in enumerate(ELEMENTS):
            for j, element in enumerate(row):
                if element:
                    w = tk.Checkbutton(self.ui_periodic_table, text=element,
                                       variable=self.var_elements[element],
                                       command=self._cb_elements_changed)
                    self.ui_elements[element] = w
                else:
                    w = tk.Label(self.ui_periodic_table)
                w.grid(row=i, column=j, sticky='w')

        self.ui_output_frame = tk.LabelFrame(self.canvas, text='Basis set')
        self.ui_output_frame.grid(row=1, column=1, columnspan=4, sticky='news', pady=5, padx=5)
        self.ui_output = Pmw.ScrolledText(self.ui_output_frame, text_state='disabled',
                                          text_padx=4, text_pady=4, usehullsize=True,
                                          hull_width=300, hull_height=200, text_font='Courier')
        self.ui_output.pack(expand=True, fill='both')

        self.ui_saved_basis_frame = tk.LabelFrame(self.canvas, text='Your saved basis sets')
        self.ui_saved_basis = Pmw.ScrolledListBox(self.ui_saved_basis_frame,
                                                  items=sorted(self.saved_basis.keys()))
        self.ui_saved_basis_add = tk.Button(self.ui_saved_basis_frame, text='Add current',
                                            command=self._cb_saved_basis_add)
        self.ui_saved_basis_del = tk.Button(self.ui_saved_basis_frame, text='Delete',
                                            command=self._cb_saved_basis_del)
        self.ui_saved_basis_frame.grid(row=1, column=5, sticky='news', pady=5, padx=5)
        self.ui_saved_basis.grid(row=0, column=0, columnspan=2, sticky='news', pady=2, padx=2)
        self.ui_saved_basis_add.grid(row=1, column=0, sticky='we', pady=2, padx=2)
        self.ui_saved_basis_del.grid(row=1, column=1, sticky='we', pady=2, padx=2)

    # Callbacks & Actions
    def Copy(self, *args):
        contents = self.ui_output.getvalue()
        if contents:
            self.uiMaster().clipboard_clear()
            self.uiMaster().clipboard_append(contents)
            self.status('Copied to clipboard!', blankAfter=3)

    def _cb_basissets_changed(self):
        self._cb_selection_changed()

    def _cb_elements_changed(self):
        self._refresh_basis_sets()
        self._cb_selection_changed()

    def _cb_selection_changed(self):
        self.ui_output.settext("")
        basis = self._selected_basis_set()
        if not basis:
            return
        selected_elem = self._selected_elements()
        supported_elem = self._cb_supported_elements(basis)
        elements = [e for e in selected_elem if e in supported_elem]
        text = self.get_basis_set(basis, elements)
        self.ui_output.settext(text)

    def _cb_supported_elements(self, basis_set=None):
        if basis_set is None:
            basis_set = self._selected_basis_set()
        elements = self.db.get_available_elements(basis_set)
        self._restore_periodic_table()
        for e in elements:
            if e:
                self.ui_elements[e]['fg'] = 'blue'
        return elements

    def _cb_saved_basis_add(self):
        basis_text = self.ui_output.getvalue()
        if basis_text:
            elements = tuple(sorted(self._selected_elements()))
            if not elements:
                elements = ('*',)
            self.saved_basis[elements] = basis_text
            self.ui_saved_basis.setlist(sorted(self.saved_basis.keys()))

    def _cb_saved_basis_del(self):
        item = self.ui_saved_basis.getvalue()
        for i in item:
            try:
                del self.saved_basis[tuple(i)]
            except KeyError:
                pass
        self.ui_saved_basis.setlist(sorted(self.saved_basis.keys()))

    # Helpers
    def get_basis_set(self, basis_set, elements=()):
        try:
            basis = self.db.get_basis(basis_set, elements=elements)
        except UnboundLocalError:
            return ""
        return '\n'.join([b.replace('****\n', '****\n-') for b in basis])

    def _selected_basis_set(self):
        try:
            basis_set = self.ui_basis_sets.getvalue()[0]
        except IndexError:
            return
        if basis_set != '--None--':
            return basis_set

    def _selected_elements(self):
        return [name for name, var in self.var_elements.iteritems() if var.get()]

    def _restore_periodic_table(self):
        for wid in self.ui_elements.itervalues():
            wid['fg'] = 'black'

    def _refresh_basis_sets(self):
        current = self._selected_basis_set()
        elements = self._selected_elements()
        basis_sets = self.db.get_available_basis_sets(elements=elements)
        basis_sets_names = [b for (b, _) in basis_sets]
        self.ui_basis_sets.setlist(basis_sets_names)
        if current and current in basis_sets_names:
            self.ui_basis_sets.setvalue([current])

    def _reset_all(self):
        for var in self.var_elements.itervalues():
            var.set(0)
        for wid in self.ui_elements.itervalues():
            wid['fg'] = 'black'
        self.ui_basis_sets.setlist(self.db_basissets)
        self.ui_output.settext("")


class ONIOMLayersDialog(PlumeBaseDialog):

    """
    Define ONIOM Layers on a per-atom basis
    """

    buttons = ('OK', 'Close')

    def __init__(self, saved_layers=None, *args, **kwargs):
        # Fire up
        self.title = 'Define ONIOM layers'
        self.atoms2rows = {}
        self.layers = saved_layers
        super(ONIOMLayersDialog, self).__init__(with_logo=False, *args, **kwargs)
        if saved_layers:
            self.restore_dialog(saved_layers['molecule'], saved_layers['atoms'])
    
    def fill_in_ui(self, *args):
        self.canvas.columnconfigure(0, weight=1)

        row = 1
        self.ui_molecule = MoleculeOptionMenu(self.canvas, command=self.populate_table)
        self.ui_molecule.grid(row=row, padx=5, pady=5, sticky='we')
        row +=1
        self.ui_toolbar_frame = tk.LabelFrame(self.canvas, text='Selection tools')
        self.ui_toolbar_frame.grid(row=row, padx=5, pady=5, sticky='w')
        self.ui_select_all = tk.Button(self.canvas, text='All', command=self._cb_select_all)
        self.ui_select_none = tk.Button(self.canvas, text='None', command=self._cb_select_none)
        self.ui_select_invert = tk.Button(self.canvas, text='Invert', command=self._cb_select_invert)
        self.ui_select_selection = tk.Button(self.canvas, text='Current', command=self._cb_select_selection)
        self.ui_batch_layer_entry = Pmw.EntryField(self.canvas, labelpos='w', entry_width=3,
                                                   label_text='Layer for selected:',
                                                   validate=_SortableTableWithEntries._validate_layer)
        self.ui_batch_layer_btn = tk.Button(self.canvas, text='Set',
                                            command=self._cb_batch_layer_btn)
        toolbar = [[self.ui_select_all, self.ui_select_none, self.ui_select_invert, 
                   self.ui_select_selection, (self.ui_batch_layer_entry, self.ui_batch_layer_btn)]]
        self.auto_grid(self.ui_toolbar_frame, toolbar, padx=3, pady=5, sticky='w')

        row += 1
        self.canvas.rowconfigure(row, weight=1)
        self.ui_table = t = _SortableTableWithEntries(self.canvas)
        self.ui_table.grid(row=row, padx=5, pady=5, sticky='news')
        kw = dict(anchor='w', refresh=False)
        t.addColumn('#', 'serial', format="%d", headerPadX=5, **kw)
        t.addColumn('Atom', 'atom', format=str, headerPadX=75, **kw)
        t.addColumn('Element', 'element', headerPadX=5, **kw)
        t.addColumn('Type', 'idatmtype', format=str, headerPadX=5, **kw)
        t.addColumn('Layer', 'var_layer', format=lambda a: a, headerPadX=5, **kw)
        t.addColumn('Link', 'link', format=bool, headerPadX=5, **kw)
        if self.ui_molecule.getvalue():
            self.ui_molecule.invoke()
        else:
            t.setData([])
        t.launch()
   
    def populate_table(self, molecule):
        atoms = molecule.atoms
        data = []
        mapping = self.atoms2rows[molecule] = {}
        for atom in atoms:
            kwargs = dict(atom=atom,
                          element=atom.element.name,
                          idatmtype=atom.idatmType,
                          serial=atom.serialNumber)
            mapping[atom] = row = _AtomTableProxy(**kwargs)
            data.append(row)
        self.ui_table.setData(data)

    def restore_dialog(self, molecule, rows):
        self.ui_molecule_dropdown.set(molecule)
        for atom, layer, link in rows:
            row = self.atoms2rows[atom]
            row.layer = layer
            row.link = link
        self.ui_table.refresh()
    
    def export_dialog(self):
        molecule = self.ui_molecule.getvalue()
        rows = [(row.atom, row.layer, row.link) for row in self.ui_table.data]
        return molecule, rows
    
    def _cb_batch_layer_btn(self, *args, **kwargs):
        layer = self.ui_batch_layer_entry.get()
        selected = self.ui_table.selected()
        for row in selected:
            row.layer = layer
        self.status('Applied layer {} to {} rows'.format(layer, len(selected)),
                    color='blue', blankAfter=3)
    
    def _cb_select_all(self, *args, **kwargs):
        hlist = self.ui_table.tixTable.hlist
        nrows = int(hlist.info_children()[-1])
        for row in xrange(nrows+1):
            hlist.selection_set(row)

    def _cb_select_none(self, *args, **kwargs):
        self.ui_table.tixTable.hlist.selection_clear()

    def _cb_select_invert(self, *args, **kwargs):
        hlist = self.ui_table.tixTable.hlist
        selected = set(hlist.info_selection())
        all_entries = set(hlist.info_children())
        self._cb_select_none()
        for row in selected ^ all_entries:
            hlist.selection_set(row)

    def _cb_select_selection(self, *args, **kwargs):
        self._cb_select_none()
        rows = [self.atoms2rows.get(atom.molecule, {}).get(atom)
                for atom in chimera.selection.currentAtoms()]
        self.ui_table.select(rows)

    def OK(self, *args, **kwargs):
        self.layers.clear()
        molecule, rows = self.export_dialog()
        for i, (atom, layer, link) in enumerate(rows):
            if not layer:
                not_filledin = len([1 for row in rows[i+1:] if not row[1]])
                raise UserError('Atom {} {} no layer defined!'.format(atom, 
                                'and {} atoms more have'.format(not_filledin) 
                                if not_filledin else 'has'))
            self.layers[atom] = layer
        self.Close()


class _AtomTableProxy(object):

    """
    Proxy object to ease the creation of table rows

    Attributes
    ----------
    atom=atom
    element=atom.element.name
    residue=str(atom.residue)
    serial=atom.serialNumber
    var_layer=tk.StringVar
    var_link=tk.IntVar
    """

    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        
        self.var_layer = tk.StringVar()
        self.var_layer.set('')
        self.var_link = tk.IntVar()
        self.var_link.set(0)

    @property
    def layer(self):
        return self.var_layer.get()
    
    @layer.setter
    def layer(self, value):
        self.var_layer.set(value.strip().upper())

    @property
    def link(self):
        return bool(self.var_link.get())

    @link.setter
    def link(self, value, *args, **kwargs):
        self.var_link.set(value)


class _SortableTableWithEntries(SortableTable):

    def _createCell(self, hlist, row, col, datum, column):
        contents = column.displayValue(datum)
        if isinstance(contents, tk.StringVar):
            entry = Pmw.EntryField(hlist, 
                                   entry_textvariable=contents, 
                                   entry_width=3,
                                   validate=self._validate_layer,
                                   **STYLES[Pmw.EntryField])
            widget = self._widgetData[(datum, column)] = entry
            hlist.item_create(row, col, itemtype="window", window=entry)
            return

        SortableTable._createCell(self, hlist, row, col, datum, column)

    @staticmethod
    def _validate_layer(text):
        if text.strip().upper() in ('H', 'L', 'M', ''):
            return Pmw.OK
        return Pmw.PARTIAL