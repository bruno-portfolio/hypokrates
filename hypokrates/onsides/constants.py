"""Constantes do módulo OnSIDES."""

from __future__ import annotations

# Store DuckDB filename
ONSIDES_DB_FILENAME = "onsides.duckdb"

# Default confidence threshold for filtering predictions
DEFAULT_MIN_CONFIDENCE = 0.5

# Label section codes
SECTION_BOXED_WARNING = "BW"
SECTION_WARNINGS_PRECAUTIONS = "WP"
SECTION_ADVERSE_REACTIONS = "AR"

# CSV file names inside the OnSIDES ZIP
CSV_PRODUCT_LABEL = "product_label.csv"
CSV_PRODUCT_ADVERSE_EFFECT = "product_adverse_effect.csv"
CSV_PRODUCT_TO_RXNORM = "product_to_rxnorm.csv"
CSV_RXNORM_PRODUCT = "vocab_rxnorm_product.csv"
CSV_RXNORM_INGREDIENT_TO_PRODUCT = "vocab_rxnorm_ingredient_to_product.csv"
CSV_RXNORM_INGREDIENT = "vocab_rxnorm_ingredient.csv"
CSV_MEDDRA_ADVERSE_EFFECT = "vocab_meddra_adverse_effect.csv"
