-- Allow 'steer' as a valid animal_type.
alter table animals
  drop constraint if exists animals_animal_type_check;

alter table animals
  add constraint animals_animal_type_check
  check (animal_type in ('calf', 'cow', 'bull', 'sire', 'steer'));
