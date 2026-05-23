import { ObjectWithId } from './object-with-id'

export interface DocumentBundleItem extends ObjectWithId {
  document: number
  document_title?: string
  order_id: number
  bundle_item_name: string
  created?: string
}

export interface DocumentBundle extends ObjectWithId {
  bundle_id?: string
  created?: string
  items?: DocumentBundleItem[]
  documents?: number[]
  create_items?: {
    document: number
    bundle_item_name?: string
  }[]
}

export interface DocumentBundleDocumentSummary {
  membership_id: number
  document: number
  order_id: number
  bundle_item_name: string
  title: string
}

export interface DocumentBundleSummary {
  id: number
  bundle_id: string
  current_membership_id: number
  current_order_id: number
  current_bundle_item_name: string
  items: DocumentBundleDocumentSummary[]
}
