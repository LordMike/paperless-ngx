import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import {
  DocumentBundle,
  DocumentBundleItem,
} from 'src/app/data/document-bundle'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class DocumentBundleService extends AbstractPaperlessService<DocumentBundle> {
  constructor() {
    super()
    this.resourceName = 'bundles'
  }

  createFromDocuments(documentIds: number[]): Observable<DocumentBundle> {
    this.clearCache()
    return this.http.post<DocumentBundle>(this.getResourceUrl(), {
      documents: documentIds,
    })
  }

  addDocument(
    bundleId: number,
    documentId: number,
    bundleItemName?: string
  ): Observable<DocumentBundleItem> {
    this.clearCache()
    return this.http.post<DocumentBundleItem>(
      this.getResourceUrl(bundleId, 'documents'),
      {
        document: documentId,
        bundle_item_name: bundleItemName,
      }
    )
  }

  updateMembership(
    bundleId: number,
    membershipId: number,
    bundleItemName: string
  ): Observable<DocumentBundleItem> {
    this.clearCache()
    return this.http.patch<DocumentBundleItem>(
      `${this.getResourceUrl(bundleId, 'documents')}${membershipId}/`,
      {
        bundle_item_name: bundleItemName,
      }
    )
  }

  removeMembership(bundleId: number, membershipId: number): Observable<void> {
    this.clearCache()
    return this.http.delete<void>(
      `${this.getResourceUrl(bundleId, 'documents')}${membershipId}/`
    )
  }

  reorder(
    bundleId: number,
    membershipIds: number[]
  ): Observable<DocumentBundle> {
    this.clearCache()
    return this.http.patch<DocumentBundle>(
      this.getResourceUrl(bundleId, 'order'),
      {
        membership_ids: membershipIds,
      }
    )
  }
}
