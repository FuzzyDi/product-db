export interface Product {
  product_id: string;
  status: string;
  name_raw: string | null;
  name_canonical: string | null;
  name_pos: string | null;
  name_receipt: string | null;
  brand_name: string | null;
  brand_id: number | null;
  product_type_id: number | null;
  quantity_value: string | null;
  quantity_unit: string | null;
  package_code: string | null;
  mxik_code: string | null;
  mxik_package_code: number | null;
  mxik_is_group_code: boolean | null;
  mxik_confidence: string | null;
  label_required: number | null;
  label_for_check: number | null;
  cash_sale: number | null;
  confidence_score: string | null;
  completeness_score: string | null;
  issues: string[] | null;
  review_required: boolean;
  review_reasons: string[] | null;
}

export interface MxikItem {
  mxik: string;
  name_ru: string;
  name_lat: string | null;
  international_code: string | null;
  is_group_code: boolean;
  label: number;
  label_for_check: number;
  cash_sale: number;
}

export interface MxikPackage {
  code: number;
  package_type: number;
  name_ru: string | null;
  name_lat: string | null;
}

export interface Brand {
  id: number;
  name_canonical: string;
  manufacturer_id: number | null;
}

export interface ProductType {
  id: number;
  name_ru: string;
  name_uz_latn: string | null;
  keywords_ru: string[] | null;
}

export interface PipelineStats {
  total_products: number;
  by_status: Record<string, number>;
  review_queue_size: number;
  with_brand: number;
  with_mxik: number;
  with_barcode: number;
}

export interface MxikHealth {
  last_sync_status: string | null;
  last_sync_at: string | null;
  total_records: number;
  active_records: number;
}

export interface ReviewDetail {
  product: Product;
  mxik_candidates: Array<{
    mxik: string;
    mxik_name_ru: string;
    international_code: string | null;
    rank: number;
  }>;
  similar_products: Array<{
    product_id: string;
    name_canonical: string;
    brand_name: string | null;
    sim: number;
  }>;
}
