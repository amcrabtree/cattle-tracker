-- Add bangs_tag to the animals table.
-- A Bangs tag is the official brucellosis vaccination ID issued to heifers.
alter table animals
  add column if not exists bangs_tag text;
