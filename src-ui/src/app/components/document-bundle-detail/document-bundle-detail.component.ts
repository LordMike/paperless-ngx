import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { Component, inject, OnInit } from '@angular/core'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  DocumentBundle,
  DocumentBundleItem,
} from 'src/app/data/document-bundle'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentBundleService } from 'src/app/services/rest/document-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { DocumentBundleItemEditDialogComponent } from '../document-bundle-item-edit-dialog/document-bundle-item-edit-dialog.component'

@Component({
  selector: 'pngx-document-bundle-detail',
  templateUrl: './document-bundle-detail.component.html',
  styleUrls: ['./document-bundle-detail.component.scss'],
  imports: [
    RouterModule,
    NgxBootstrapIconsModule,
    PageHeaderComponent,
    CustomDatePipe,
    DragDropModule,
  ],
})
export class DocumentBundleDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly bundleService = inject(DocumentBundleService)
  private readonly toastService = inject(ToastService)
  private readonly modalService = inject(NgbModal)

  bundle: DocumentBundle
  orderSaving = false

  ngOnInit(): void {
    this.load()
  }

  load() {
    const id = +this.route.snapshot.paramMap.get('id')
    this.bundleService.get(id).subscribe({
      next: (bundle) => {
        this.bundle = bundle
      },
      error: (error) =>
        this.toastService.showError($localize`Error loading bundle`, error),
    })
  }

  editItem(item: DocumentBundleItem) {
    const modal = this.modalService.open(
      DocumentBundleItemEditDialogComponent,
      {
        backdrop: 'static',
      }
    )
    modal.componentInstance.item = item
    modal.componentInstance.saved.subscribe(
      ({
        bundle_item_name,
        bundle_item_type,
      }: {
        bundle_item_name: string
        bundle_item_type: string
      }) => {
        this.bundleService
          .updateMembership(
            this.bundle.id,
            item.id,
            bundle_item_name,
            bundle_item_type
          )
          .subscribe({
            next: () => {
              modal.close()
              this.load()
            },
            error: (error) =>
              this.toastService.showError(
                $localize`Error updating bundle`,
                error
              ),
          })
      }
    )
  }

  remove(item: DocumentBundleItem) {
    this.bundleService.removeMembership(this.bundle.id, item.id).subscribe({
      next: () => this.load(),
      error: (error) =>
        this.toastService.showError($localize`Error updating bundle`, error),
    })
  }

  drop(event: CdkDragDrop<DocumentBundleItem[]>) {
    if (!this.bundle?.items || event.previousIndex === event.currentIndex) {
      return
    }
    moveItemInArray(this.bundle.items, event.previousIndex, event.currentIndex)
    const membershipIds = this.bundle.items.map((item) => item.id)
    this.orderSaving = true
    this.bundleService.reorder(this.bundle.id, membershipIds).subscribe({
      next: () => {
        this.orderSaving = false
        this.load()
      },
      error: (error) => {
        this.orderSaving = false
        this.load()
        this.toastService.showError(
          $localize`Error updating bundle order`,
          error
        )
      },
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
