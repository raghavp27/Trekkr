"""Add continent column to regions_country

Revision ID: 20251229_0008
Revises: 20251229_0007
Create Date: 2024-12-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '20251229_0008'
down_revision = '20251229_0007'
branch_labels = None
depends_on = None


# UN geoscheme continent assignments by ISO2 code
CONTINENT_MAPPING = {
    'Africa': [
        'DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CV', 'CM', 'CF', 'TD', 'KM', 'CG', 'CD', 'CI', 'DJ',
        'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW', 'KE', 'LS', 'LR', 'LY', 'MG',
        'MW', 'ML', 'MR', 'MU', 'YT', 'MA', 'MZ', 'NA', 'NE', 'NG', 'RE', 'RW', 'ST', 'SN', 'SC',
        'SL', 'SO', 'ZA', 'SS', 'SD', 'TZ', 'TG', 'TN', 'UG', 'EH', 'ZM', 'ZW', 'SH'
    ],
    'Antarctica': ['AQ', 'BV', 'GS', 'HM', 'TF'],
    'Asia': [
        'AF', 'AM', 'AZ', 'BH', 'BD', 'BT', 'BN', 'KH', 'CN', 'CY', 'GE', 'HK', 'IN', 'ID', 'IR',
        'IQ', 'IL', 'JP', 'JO', 'KZ', 'KW', 'KG', 'LA', 'LB', 'MO', 'MY', 'MV', 'MN', 'MM', 'NP',
        'KP', 'OM', 'PK', 'PS', 'PH', 'QA', 'SA', 'SG', 'KR', 'LK', 'SY', 'TW', 'TJ', 'TH', 'TL',
        'TR', 'TM', 'AE', 'UZ', 'VN', 'YE', 'CC', 'CX', 'IO'
    ],
    'Europe': [
        'AL', 'AD', 'AT', 'BY', 'BE', 'BA', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FO', 'FI', 'FR', 'DE',
        'GI', 'GR', 'GL', 'GG', 'HU', 'IS', 'IE', 'IM', 'IT', 'JE', 'XK', 'LV', 'LI', 'LT', 'LU',
        'MT', 'MD', 'MC', 'ME', 'NL', 'MK', 'NO', 'PL', 'PT', 'RO', 'RU', 'SM', 'RS', 'SK', 'SI',
        'ES', 'SJ', 'SE', 'CH', 'UA', 'GB', 'VA', 'AX'
    ],
    'North America': [
        'AI', 'AG', 'AW', 'BS', 'BB', 'BZ', 'BM', 'BQ', 'VG', 'CA', 'KY', 'CR', 'CU', 'CW', 'DM',
        'DO', 'SV', 'GD', 'GP', 'GT', 'HT', 'HN', 'JM', 'MQ', 'MX', 'MS', 'NI', 'PA', 'PR', 'BL',
        'KN', 'LC', 'MF', 'PM', 'VC', 'SX', 'TT', 'TC', 'US', 'VI'
    ],
    'Oceania': [
        'AS', 'AU', 'CK', 'FJ', 'PF', 'GU', 'KI', 'MH', 'FM', 'NR', 'NC', 'NZ', 'NU', 'NF', 'MP',
        'PW', 'PG', 'PN', 'WS', 'SB', 'TK', 'TO', 'TV', 'UM', 'VU', 'WF'
    ],
    'South America': [
        'AR', 'BO', 'BR', 'CL', 'CO', 'EC', 'FK', 'GF', 'GY', 'PY', 'PE', 'SR', 'UY', 'VE'
    ],
}


def upgrade():
    """Add continent column and populate based on UN geoscheme."""
    # Add nullable column first
    op.add_column('regions_country', sa.Column('continent', sa.String(32), nullable=True))

    # Populate continent values using parameterized queries
    conn = op.get_bind()
    for continent, iso2_codes in CONTINENT_MAPPING.items():
        if iso2_codes:
            # Use parameterized query with bound parameters for safety
            conn.execute(
                text("""
                    UPDATE regions_country
                    SET continent = :continent
                    WHERE iso2 = ANY(:iso2_codes)
                """),
                {"continent": continent, "iso2_codes": iso2_codes}
            )

    # Set any remaining countries to 'Unknown' (shouldn't happen with complete mapping)
    conn.execute(text("""
        UPDATE regions_country
        SET continent = 'Unknown'
        WHERE continent IS NULL
    """))

    # Make column non-nullable
    op.alter_column('regions_country', 'continent', nullable=False)


def downgrade():
    """Remove continent column."""
    op.drop_column('regions_country', 'continent')
