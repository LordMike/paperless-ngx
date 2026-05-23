import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import { NgbModal, NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, debounceTime, distinctUntilChanged, takeUntil } from 'rxjs'
import { ConfirmDialogComponent } from 'src/app/components/common/confirm-dialog/confirm-dialog.component'
import { DocumentBundleEditDialogComponent } from 'src/app/components/document-bundle-edit-dialog/document-bundle-edit-dialog.component'
import { DocumentBundle } from 'src/app/data/document-bundle'
import {
  SortEvent,
  SortableDirective,
} from 'src/app/directives/sortable.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentBundleService } from 'src/app/services/rest/document-bundle.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-document-bundle-list',
  templateUrl: './document-bundle-list.component.html',
  imports: [
    FormsModule,
    RouterModule,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
    SortableDirective,
    CustomDatePipe,
  ],
})
export class DocumentBundleListComponent implements OnInit, OnDestroy {
  private readonly bundleService = inject(DocumentBundleService)
  private readonly modalService = inject(NgbModal)
  private readonly toastService = inject(ToastService)
  private readonly unsubscribeNotifier = new Subject<void>()
  private readonly filterDebounce = new Subject<string>()

  bundles: DocumentBundle[] = []
  loading = true
  show = false
  page = 1
  pageSize = 25
  collectionSize = 0
  sortField = 'bundle_id'
  sortReverse = false
  bundleIdFilter = ''

  ngOnInit(): void {
    this.filterDebounce
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        debounceTime(400),
        distinctUntilChanged()
      )
      .subscribe((value) => {
        this.bundleIdFilter = value
        this.page = 1
        this.reloadData()
      })
    this.reloadData()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  reloadData(): void {
    this.loading = true
    this.bundleService
      .list(this.page, this.pageSize, this.sortField, this.sortReverse, {
        bundle_id__icontains: this.bundleIdFilter,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (results) => {
          this.bundles = results.results
          this.collectionSize = results.count
          this.loading = false
          this.show = true
        },
        error: (error) => {
          this.loading = false
          this.toastService.showError($localize`Error loading bundles`, error)
        },
      })
  }

  onSort(event: SortEvent): void {
    this.sortField = event.column
    this.sortReverse = event.reverse
    this.reloadData()
  }

  onFilterKeyUp(event: KeyboardEvent): void {
    const input = event.target as HTMLInputElement
    if (event.code === 'Escape') {
      input.value = ''
      this.filterDebounce.next('')
      return
    }
    this.filterDebounce.next(input.value)
  }

  openEditDialog(bundle: DocumentBundle): void {
    const modal = this.modalService.open(DocumentBundleEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.bundle = bundle
    modal.componentInstance.saved.subscribe(({ bundle_id }) => {
      this.bundleService.patch({ ...bundle, bundle_id }).subscribe({
        next: () => {
          modal.close()
          this.reloadData()
          this.toastService.showInfo(
            $localize`Successfully updated bundle "${bundle_id}".`
          )
        },
        error: (error) =>
          this.toastService.showError($localize`Error updating bundle`, error),
      })
    })
  }

  openDeleteDialog(bundle: DocumentBundle): void {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = $localize`Delete bundle "${bundle.bundle_id}"?`
    modal.componentInstance.message = $localize`Documents will not be removed. Only the bundle and its document membership records will be deleted.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.bundleService.delete(bundle).subscribe({
        next: () => {
          modal.close()
          this.reloadData()
        },
        error: (error) => {
          modal.componentInstance.buttonsEnabled = true
          this.toastService.showError($localize`Error deleting bundle`, error)
        },
      })
    })
  }
}
