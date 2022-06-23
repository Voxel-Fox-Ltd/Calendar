CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


CREATE TABLE IF NOT EXISTS guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix TEXT,
    calendar_message_url TEXT
);
-- A default guild settings table.
-- This is required for VBU and should not be deleted.
-- You can add more columns to this table should you want to add more guild-specific
-- settings.


CREATE TABLE IF NOT EXISTS user_settings(
    user_id BIGINT PRIMARY KEY
);
-- A default guild settings table.
-- This is required for VBU and should not be deleted.
-- You can add more columns to this table should you want to add more user-specific
-- settings.
-- This table is not suitable for member-specific settings as there's no
-- guild ID specified.


DO $$ BEGIN
    CREATE TYPE repeat_time AS ENUM(
        'daily',
        'weekly',
        'monthly',
        'yearly'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


CREATE TABLE IF NOT EXISTS guild_events(
    id UUID NOT NULL PRIMARY KEY,  -- the ID of the event
    guild_id BIGINT NOT NULL,  -- the ID of the guild it's attached to
    user_id BIGINT NOT NULL,  -- the ID of the user who added this event
    name TEXT NOT NULL,  -- the name of the event
    timestamp TIMESTAMP NOT NULL,  -- when the event is initially to start
    repeat repeat_time  -- how often the event repeats
);
