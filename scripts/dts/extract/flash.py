#
# Copyright (c) 2018 Bobby Noelte
#
# SPDX-License-Identifier: Apache-2.0
#

from extract.globals import *
from extract.directive import DTDirective

from extract.default import default
from extract.reg import reg

##
# @brief Manage flash directives.
#
class DTFlash(DTDirective):

    def __init__(self):
        # Node of the flash
        self._flash_node = None

    def extract_partition(self, node_address):
        prop_def = {}
        prop_alias = {}
        node = reduced[node_address]

        partition_name = node['props']['label']
        partition_sectors = node['props']['reg']

        label_prefix = ["FLASH_AREA", partition_name]
        label = self.get_label_string(label_prefix + ["LABEL",])
        prop_def[label] = '"{}"'.format(partition_name)

        label = self.get_label_string(label_prefix + ["READ_ONLY",])
        prop_def[label] = 1 if 'read-only' in node['props'] else 0

        index = 0
        while index < len(partition_sectors):
            sector_index = int(index/2)
            sector_start_offset = partition_sectors[index]
            sector_size = partition_sectors[index + 1]
            label = self.get_label_string(
                label_prefix + ["OFFSET", str(sector_index)])
            prop_def[label] = "{}".format(sector_start_offset)
            label = self.get_label_string(
                label_prefix + ["SIZE", str(sector_index)])
            prop_def[label] = "{}".format(sector_size)
            index += 2
        # alias sector 0
        label = self.get_label_string(label_prefix + ["OFFSET",])
        prop_alias[label] = self.get_label_string(
            label_prefix + ["OFFSET", '0'])
        label = self.get_label_string(label_prefix + ["SIZE",])
        prop_alias[label] = self.get_label_string(
            label_prefix + ["SIZE", '0'])

        insert_defs(node_address, prop_def, prop_alias)

    def _extract_flash(self, node_address, prop, def_label):
        if node_address == 'dummy-flash':
            # We will add addr/size of 0 for systems with no flash controller
            # This is what they already do in the Kconfig options anyway
            insert_defs(node_address,
                        {'DT_FLASH_BASE_ADDRESS': 0, 'DT_FLASH_SIZE': 0},
                        {})
            self._flash_base_address = 0
            return

        self._flash_node = reduced[node_address]
        orig_node_addr = node_address

        (nr_address_cells, nr_size_cells) = get_addr_size_cells(node_address)
        # if the nr_size_cells is 0, assume a SPI flash, need to look at parent
        # for addr/size info, and the second reg property (assume first is mmio
        # register for the controller itself)
        is_spi_flash = False
        if nr_size_cells == 0:
            is_spi_flash = True
            node_address = get_parent_address(node_address)
            (nr_address_cells, nr_size_cells) = get_addr_size_cells(node_address)

        node_compat = get_compat(node_address)
        reg = reduced[node_address]['props']['reg']
        if type(reg) is not list: reg = [ reg, ]
        props = list(reg)

        num_reg_elem = len(props)/(nr_address_cells + nr_size_cells)

        # if we found a spi flash, but don't have mmio direct access support
        # which we determin by the spi controller node only have on reg element
        # (ie for the controller itself and no region for the MMIO flash access)
        if num_reg_elem == 1 and is_spi_flash:
            node_address = orig_node_addr
        else:
            # We assume the last reg property is the one we want
            while props:
                addr = 0
                size = 0

                for x in range(nr_address_cells):
                    addr += props.pop(0) << (32 * (nr_address_cells - x - 1))
                for x in range(nr_size_cells):
                    size += props.pop(0) << (32 * (nr_size_cells - x - 1))

            addr += translate_addr(addr, node_address, nr_address_cells,
                                   nr_size_cells)

            insert_defs(node_address,
                        {'DT_FLASH_BASE_ADDRESS': hex(addr),
                         'DT_FLASH_SIZE': size//1024},
                        {})

        for prop in 'label', 'write-block-size', 'erase-block-size':
            if prop in self._flash_node['props']:
                default.extract(node_address, prop, None, def_label)

    def _extract_code_partition(self, node_address, prop, def_label):
        if node_address == 'dummy-flash':
            node = None
        else:
            node = reduced[node_address]
            if self._flash_node is None:
                # No flash node scanned before-
                raise Exception(
                    "Code partition '{}' {} without flash definition."
                        .format(prop, node_address))

        if node and node is not self._flash_node:
            # only compute the load offset if the code partition
            # is not the same as the flash base address
            load_offset = node['props']['reg'][0]
            load_size = node['props']['reg'][1]
        else:
            load_offset = 0
            load_size = 0

        insert_defs(node_address,
                    {'DT_CODE_PARTITION_OFFSET': load_offset,
                     'DT_CODE_PARTITION_SIZE': load_size},
                    {})

    ##
    # @brief Extract flash
    #
    # @param node_address Address of node owning the
    #                     flash definition.
    # @param prop compatible property name
    # @param def_label Define label string of node owning the
    #                  compatible definition.
    #
    def extract(self, node_address, prop, def_label):

        if prop == 'zephyr,flash':
            # indicator for flash
            self._extract_flash(node_address, prop, def_label)
        elif prop == 'zephyr,code-partition':
            # indicator for code_partition
            self._extract_code_partition(node_address, prop, def_label)
        else:
            raise Exception(
                "DTFlash.extract called with unexpected directive ({})."
                    .format(prop))
##
# @brief Management information for flash.
flash = DTFlash()
