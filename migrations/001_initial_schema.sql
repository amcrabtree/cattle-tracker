-- ── Extensions ────────────────────────────────────────────────────────────────
create extension if not exists "pgcrypto";

-- ── updated_at trigger function ───────────────────────────────────────────────
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ── 1. animals ────────────────────────────────────────────────────────────────
create table if not exists animals (
  id               uuid        primary key default gen_random_uuid(),
  registration_num text        unique,
  phn              text,                         -- e.g. "SPAD 28N"
  tag              text,                         -- e.g. "28N"
  name             text,                         -- sire display names e.g. "GROWTH FUND"
  animal_type      text        not null check (animal_type in ('calf','cow','bull','sire','steer')),
  sex              text        check (sex in ('M','F')),
  color            text,
  dob              date,
  status           text        not null default 'active'
                               check (status in ('active','dead','sold')),
  dam_id           uuid        references animals(id) on delete set null,
  sire_id          uuid        references animals(id) on delete set null,
  bangs_tag        text,                         -- official brucellosis vaccination tag (heifers only)
  notes            text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists animals_tag_idx              on animals(tag);
create index if not exists animals_registration_num_idx on animals(registration_num);
create index if not exists animals_phn_idx              on animals(phn);
create index if not exists animals_status_idx           on animals(status);
create index if not exists animals_animal_type_idx      on animals(animal_type);
create index if not exists animals_dam_id_idx           on animals(dam_id);
create index if not exists animals_sire_id_idx          on animals(sire_id);

create or replace trigger animals_updated_at
  before update on animals
  for each row execute function set_updated_at();

-- ── 2. weight_records ─────────────────────────────────────────────────────────
create table if not exists weight_records (
  id          uuid        primary key default gen_random_uuid(),
  animal_id   uuid        not null references animals(id) on delete cascade,
  weight_date date        not null,
  weight_lbs  numeric     not null check (weight_lbs > 0),
  category    text        not null check (category in ('weaning','yearly','routine')),
  notes       text,
  created_at  timestamptz not null default now()
);

create index if not exists weight_records_animal_id_idx   on weight_records(animal_id);
create index if not exists weight_records_weight_date_idx on weight_records(weight_date);
create index if not exists weight_records_category_idx    on weight_records(category);

-- ── 3. vaccinations ───────────────────────────────────────────────────────────
create table if not exists vaccinations (
  id                uuid        primary key default gen_random_uuid(),
  animal_id         uuid        not null references animals(id) on delete cascade,
  vaccine_name      text        not null,
  administered_date date        not null,
  administered_by   text,
  next_due_date     date,
  lot_number        text,
  notes             text,
  created_at        timestamptz not null default now()
);

create index if not exists vaccinations_animal_id_idx       on vaccinations(animal_id);
create index if not exists vaccinations_next_due_date_idx   on vaccinations(next_due_date);
create index if not exists vaccinations_vaccine_name_idx    on vaccinations(vaccine_name);

-- ── 4. health_events ─────────────────────────────────────────────────────────
create table if not exists health_events (
  id            uuid        primary key default gen_random_uuid(),
  animal_id     uuid        not null references animals(id) on delete cascade,
  event_date    date        not null,
  event_type    text        not null check (event_type in ('illness','treatment','vet_visit','injury','other')),
  description   text        not null,
  treatment     text,
  medication    text,
  veterinarian  text,
  resolved_date date,
  notes         text,
  created_at    timestamptz not null default now()
);

create index if not exists health_events_animal_id_idx   on health_events(animal_id);
create index if not exists health_events_event_date_idx  on health_events(event_date);
create index if not exists health_events_event_type_idx  on health_events(event_type);
-- Partial index speeds up "active issues" query (unresolved events only)
create index if not exists health_events_resolved_idx    on health_events(resolved_date) where resolved_date is null;

-- ── 5. breeding_records ───────────────────────────────────────────────────────
create table if not exists breeding_records (
  id                    uuid        primary key default gen_random_uuid(),
  dam_id                uuid        not null references animals(id) on delete restrict,
  sire_id               uuid        not null references animals(id) on delete restrict,
  breeding_date         date,
  expected_calving_date date,
  actual_calving_date   date,
  calf_id               uuid        references animals(id) on delete set null,
  outcome               text        check (outcome in ('live_birth','stillbirth','abort','pending')),
  notes                 text,
  created_at            timestamptz not null default now()
);

create index if not exists breeding_records_dam_id_idx  on breeding_records(dam_id);
create index if not exists breeding_records_sire_id_idx on breeding_records(sire_id);
create index if not exists breeding_records_calf_id_idx on breeding_records(calf_id);

-- ── RLS ───────────────────────────────────────────────────────────────────────
-- Service-role key bypasses RLS; no permissive policies = anon/authenticated denied
alter table animals          enable row level security;
alter table weight_records   enable row level security;
alter table vaccinations     enable row level security;
alter table health_events    enable row level security;
alter table breeding_records enable row level security;
