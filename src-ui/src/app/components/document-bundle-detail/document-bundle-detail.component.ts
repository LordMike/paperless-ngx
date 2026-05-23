import { Component, inject, OnInit } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  DocumentBundle,
  DocumentBundleItem,
} from 'src/app/data/document-bundle'
import { DocumentBundleService } from 'src/app/services/rest/document-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { PageHeaderComponent } from '../common/page-header/page-header.component'

@Component({
  selector: 'pngx-document-bundle-detail',
  templateUrl: './document-bundle-detail.component.html',
  styleUrls: ['./document-bundle-detail.component.scss'],
  imports: [
    FormsModule,
    RouterModule,
    NgxBootstrapIconsModule,
    PageHeaderComponent,
  ],
})
export class DocumentBundleDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly bundleService = inject(DocumentBundleService)
  private readonly toastService = inject(ToastService)

  bundle: DocumentBundle
  addDocumentId: number
  orderEdits: Record<number, number> = {}

  ngOnInit(): void {
    this.load()
  }

  load() {
    const id = +this.route.snapshot.paramMap.get('id')
    this.bundleService.get(id).subscribe({
      next: (bundle) => {
        this.bundle = bundle
        this.orderEdits = {}
        bundle.items?.forEach(
          (item) => (this.orderEdits[item.id] = item.order_id)
        )
      },
      error: (error) =>
        this.toastService.showError($localize`Error loading bundle`, error),
    })
  }

  openDocument(item: DocumentBundleItem) {
    this.router.navigate(['documents', item.document])
  }

  addDocument() {
    if (!this.addDocumentId) return
    this.bundleService
      .addDocument(this.bundle.id, this.addDocumentId)
      .subscribe({
        next: () => {
          this.addDocumentId = null
          this.load()
        },
        error: (error) =>
          this.toastService.showError($localize`Error adding document`, error),
      })
  }

  editName(item: DocumentBundleItem) {
    const name = window.prompt(
      $localize`Bundle item name`,
      item.bundle_item_name
    )
    if (name === null) return
    this.bundleService
      .updateMembership(this.bundle.id, item.id, name)
      .subscribe({
        next: () => this.load(),
        error: (error) =>
          this.toastService.showError($localize`Error updating bundle`, error),
      })
  }

  remove(item: DocumentBundleItem) {
    this.bundleService.removeMembership(this.bundle.id, item.id).subscribe({
      next: () => this.load(),
      error: (error) =>
        this.toastService.showError($localize`Error updating bundle`, error),
    })
  }

  saveOrder() {
    const membershipIds = [...(this.bundle.items ?? [])]
      .sort((a, b) => this.orderEdits[a.id] - this.orderEdits[b.id])
      .map((item) => item.id)
    this.bundleService.reorder(this.bundle.id, membershipIds).subscribe({
      next: () => this.load(),
      error: (error) =>
        this.toastService.showError(
          $localize`Error updating bundle order`,
          error
        ),
    })
  }

  deleteBundle() {
    if (
      !window.confirm(
        $localize`Delete this bundle? Documents will not be deleted.`
      )
    )
      return
    this.bundleService.delete(this.bundle).subscribe({
      next: () => this.router.navigate(['documents']),
      error: (error) =>
        this.toastService.showError($localize`Error deleting bundle`, error),
    })
  }
}
