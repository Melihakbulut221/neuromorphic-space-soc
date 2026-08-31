/* GENERATED FILE - edit regmap/memmap.yaml and run regmap/generate_memmap.py */

/* The ROM region starts AT the reset vector, not at the region
   base. Ibex resets to {boot_addr_i[31:8], 8'h80}, so the first
   fetched instruction is at base+0x80 and nothing may be linked
   below it -- docs/38-ibex-bringup.md section 7.5 defect 4, where
   exactly that moved _start off the reset vector and the core ran
   the program from arbitrary offsets. Expressing the offset here,
   in generated text, is what stops the next link script from
   getting it wrong. */
MEMORY {
  rom (rx)  : ORIGIN = 0xC0000080, LENGTH = 0x1F80
  ram (rwx) : ORIGIN = 0x00000000, LENGTH = 0x10000
}

__soc_reset_vector = 0xC0000080;
__soc_ram_base     = 0x00000000;
__soc_ram_top      = 0x00010000;
