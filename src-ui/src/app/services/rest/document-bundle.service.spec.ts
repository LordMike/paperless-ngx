import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { DocumentBundleService } from './document-bundle.service'

const endpoint = 'bundles'

commonAbstractPaperlessServiceTests(endpoint, DocumentBundleService)

describe('DocumentBundleService', () => {
  let httpTestingController: HttpTestingController
  let service: DocumentBundleService
  let subscription: Subscription | undefined

  beforeEach(() => {
    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(DocumentBundleService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('creates a bundle from document ids', () => {
    subscription = service.createFromDocuments([1, 2]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({ documents: [1, 2] })
    req.flush({})
  })

  it('suggests a bundle id', () => {
    subscription = service.suggestId().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/suggest_id/`
    )
    expect(req.request.method).toBe('GET')
    req.flush({ bundle_id: 'A001' })
  })

  it('creates a bundle for a document', () => {
    subscription = service
      .createForDocument(7, 'A001', 'Insurance policy')
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/create_for_document/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({
      document: 7,
      bundle_id: 'A001',
      name: 'Insurance policy',
    })
    req.flush({})
  })

  it('adds a document to a bundle', () => {
    subscription = service.addDocument(4, 7, 'schedule').subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/documents/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({
      document: 7,
      bundle_item_name: 'schedule',
    })
    req.flush({})
  })

  it('updates a membership name', () => {
    subscription = service
      .updateMembership(4, 9, 'terms', 'appendix')
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/documents/9/`
    )
    expect(req.request.method).toBe('PATCH')
    expect(req.request.body).toEqual({
      bundle_item_name: 'terms',
      bundle_item_type: 'appendix',
    })
    req.flush({})
  })

  it('removes a membership', () => {
    subscription = service.removeMembership(4, 9).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/documents/9/`
    )
    expect(req.request.method).toBe('DELETE')
    req.flush({})
  })

  it('moves a document between bundles', () => {
    subscription = service
      .moveDocument(5, 9, 'schedule', 'cover letter')
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/5/move_document/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({
      membership: 9,
      bundle_item_name: 'schedule',
      bundle_item_type: 'cover letter',
    })
    req.flush({})
  })

  it('reorders memberships', () => {
    subscription = service.reorder(4, [9, 8]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/4/order/`
    )
    expect(req.request.method).toBe('PATCH')
    expect(req.request.body).toEqual({ membership_ids: [9, 8] })
    req.flush({})
  })
})
