#include "nrtx/physx_world.h"

#include <PxPhysicsAPI.h>

#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

using namespace physx;

namespace nrtx {
namespace {

class PhysXAllocator : public PxAllocatorCallback {
public:
  void *allocate(size_t size, const char *, const char *, int) override {
#if defined(_WIN32)
    return _aligned_malloc(size, 16);
#else
    void *ptr = nullptr;
    if (posix_memalign(&ptr, 16, size) != 0) {
      return nullptr;
    }
    return ptr;
#endif
  }
  void deallocate(void *ptr) override {
#if defined(_WIN32)
    _aligned_free(ptr);
#else
    free(ptr);
#endif
  }
};

class PhysXErrorCallback : public PxErrorCallback {
public:
  void reportError(PxErrorCode::Enum, const char *message, const char *file, int line) override {
    // Keep quiet in release demos; surface in stderr for debugging.
    fprintf(stderr, "[PhysX] %s (%s:%d)\n", message, file, line);
  }
};

PxTransform to_px(const Pose &pose) {
  return PxTransform(PxVec3(pose.position.x, pose.position.y, pose.position.z),
                     PxQuat(pose.quat.x, pose.quat.y, pose.quat.z, pose.quat.w));
}

Pose from_px(const PxTransform &t) {
  Pose p;
  p.position = make_float3(t.p.x, t.p.y, t.p.z);
  p.quat = make_float4(t.q.x, t.q.y, t.q.z, t.q.w);
  return p;
}

} // namespace

struct PhysXWorld::Impl {
  PhysXAllocator allocator;
  PhysXErrorCallback error_callback;
  PxFoundation *foundation = nullptr;
  PxPhysics *physics = nullptr;
  PxDefaultCpuDispatcher *dispatcher = nullptr;
  PxCudaContextManager *cuda_manager = nullptr;
  PxScene *scene = nullptr;
  PxMaterial *material = nullptr;
  std::vector<PxRigidActor *> actors;
  bool gpu = false;
  std::string backend = "uninitialized";
  bool initialized = false;

  void shutdown() {
    for (PxRigidActor *actor : actors) {
      if (actor) {
        actor->release();
      }
    }
    actors.clear();
    if (scene) {
      scene->release();
      scene = nullptr;
    }
    if (dispatcher) {
      dispatcher->release();
      dispatcher = nullptr;
    }
    if (material) {
      material->release();
      material = nullptr;
    }
    if (physics) {
      physics->release();
      physics = nullptr;
    }
    if (cuda_manager) {
      cuda_manager->release();
      cuda_manager = nullptr;
    }
    if (foundation) {
      foundation->release();
      foundation = nullptr;
    }
    gpu = false;
    backend = "uninitialized";
    initialized = false;
  }

  ~Impl() { shutdown(); }
};

PhysXWorld::PhysXWorld() : impl_(std::make_unique<Impl>()) {}

PhysXWorld::~PhysXWorld() = default;

void PhysXWorld::init() {
  impl_->shutdown();

  impl_->foundation = PxCreateFoundation(PX_PHYSICS_VERSION, impl_->allocator, impl_->error_callback);
  if (!impl_->foundation) {
    throw std::runtime_error("PxCreateFoundation failed");
  }

  impl_->physics = PxCreatePhysics(PX_PHYSICS_VERSION, *impl_->foundation, PxTolerancesScale(), true, nullptr);
  if (!impl_->physics) {
    throw std::runtime_error("PxCreatePhysics failed");
  }

  PxCudaContextManagerDesc cuda_desc;
  impl_->cuda_manager = PxCreateCudaContextManager(*impl_->foundation, cuda_desc, PxGetProfilerCallback());
  if (impl_->cuda_manager && !impl_->cuda_manager->contextIsValid()) {
    impl_->cuda_manager->release();
    impl_->cuda_manager = nullptr;
  }
  if (!impl_->cuda_manager) {
    throw std::runtime_error(
        "PhysX GPU init failed: could not create a valid CUDA context manager. "
        "Ensure third_party/physx/bin/libPhysXGpu_64.so is on LD_LIBRARY_PATH "
        "(docker/run.sh sets this) and an NVIDIA GPU is available.");
  }

  PxSceneDesc scene_desc(impl_->physics->getTolerancesScale());
  scene_desc.gravity = PxVec3(0.0f, -9.81f, 0.0f);
  impl_->dispatcher = PxDefaultCpuDispatcherCreate(2);
  if (!impl_->dispatcher) {
    throw std::runtime_error("PxDefaultCpuDispatcherCreate failed");
  }
  scene_desc.cpuDispatcher = impl_->dispatcher;
  scene_desc.filterShader = PxDefaultSimulationFilterShader;
  scene_desc.cudaContextManager = impl_->cuda_manager;
  scene_desc.flags |= PxSceneFlag::eENABLE_GPU_DYNAMICS;
  scene_desc.flags |= PxSceneFlag::eENABLE_PCM;
  scene_desc.flags |= PxSceneFlag::eENABLE_STABILIZATION;
  scene_desc.broadPhaseType = PxBroadPhaseType::eGPU;
  scene_desc.gpuMaxNumPartitions = 8;

  impl_->scene = impl_->physics->createScene(scene_desc);
  if (!impl_->scene) {
    throw std::runtime_error("PxPhysics::createScene failed");
  }

  impl_->material = impl_->physics->createMaterial(0.5f, 0.5f, 0.4f);
  if (!impl_->material) {
    throw std::runtime_error("PxPhysics::createMaterial failed");
  }

  impl_->gpu = true;
  impl_->backend = "gpu";
  impl_->initialized = true;
}

bool PhysXWorld::using_gpu() const { return impl_->gpu; }

const std::string &PhysXWorld::backend() const { return impl_->backend; }

int PhysXWorld::add_static_box(const float3 &half_extents, const Pose &pose) {
  if (!impl_->initialized) {
    throw std::runtime_error("PhysXWorld::init must be called first");
  }
  PxRigidStatic *actor = impl_->physics->createRigidStatic(to_px(pose));
  if (!actor) {
    throw std::runtime_error("createRigidStatic failed");
  }
  PxShape *shape =
      impl_->physics->createShape(PxBoxGeometry(half_extents.x, half_extents.y, half_extents.z), *impl_->material);
  if (!shape) {
    actor->release();
    throw std::runtime_error("createShape(box) failed");
  }
  actor->attachShape(*shape);
  shape->release();
  impl_->scene->addActor(*actor);
  const int id = static_cast<int>(impl_->actors.size());
  impl_->actors.push_back(actor);
  return id;
}

int PhysXWorld::add_dynamic_box(const float3 &half_extents, float density, const Pose &pose) {
  if (!impl_->initialized) {
    throw std::runtime_error("PhysXWorld::init must be called first");
  }
  PxRigidDynamic *actor = PxCreateDynamic(*impl_->physics, to_px(pose),
                                          PxBoxGeometry(half_extents.x, half_extents.y, half_extents.z),
                                          *impl_->material, density);
  if (!actor) {
    throw std::runtime_error("PxCreateDynamic(box) failed");
  }
  actor->setAngularDamping(0.35f);
  actor->setLinearDamping(0.05f);
  impl_->scene->addActor(*actor);
  const int id = static_cast<int>(impl_->actors.size());
  impl_->actors.push_back(actor);
  return id;
}

int PhysXWorld::add_dynamic_sphere(float radius, float density, const Pose &pose) {
  if (!impl_->initialized) {
    throw std::runtime_error("PhysXWorld::init must be called first");
  }
  PxRigidDynamic *actor =
      PxCreateDynamic(*impl_->physics, to_px(pose), PxSphereGeometry(radius), *impl_->material, density);
  if (!actor) {
    throw std::runtime_error("PxCreateDynamic(sphere) failed");
  }
  actor->setAngularDamping(0.2f);
  actor->setLinearDamping(0.02f);
  impl_->scene->addActor(*actor);
  const int id = static_cast<int>(impl_->actors.size());
  impl_->actors.push_back(actor);
  return id;
}

void PhysXWorld::set_linear_velocity(int actor_id, const float3 &velocity) {
  if (actor_id < 0 || actor_id >= static_cast<int>(impl_->actors.size())) {
    throw std::out_of_range("PhysXWorld::set_linear_velocity invalid actor_id");
  }
  auto *dyn = impl_->actors[static_cast<size_t>(actor_id)]->is<PxRigidDynamic>();
  if (!dyn) {
    throw std::runtime_error("set_linear_velocity requires a dynamic actor");
  }
  dyn->setLinearVelocity(PxVec3(velocity.x, velocity.y, velocity.z));
}

void PhysXWorld::set_angular_velocity(int actor_id, const float3 &velocity) {
  if (actor_id < 0 || actor_id >= static_cast<int>(impl_->actors.size())) {
    throw std::out_of_range("PhysXWorld::set_angular_velocity invalid actor_id");
  }
  auto *dyn = impl_->actors[static_cast<size_t>(actor_id)]->is<PxRigidDynamic>();
  if (!dyn) {
    throw std::runtime_error("set_angular_velocity requires a dynamic actor");
  }
  dyn->setAngularVelocity(PxVec3(velocity.x, velocity.y, velocity.z));
}

void PhysXWorld::step(float dt, int substeps) {
  if (!impl_->initialized) {
    throw std::runtime_error("PhysXWorld::init must be called first");
  }
  if (substeps < 1) {
    throw std::invalid_argument("substeps must be >= 1");
  }
  const float h = dt / static_cast<float>(substeps);
  for (int i = 0; i < substeps; ++i) {
    impl_->scene->simulate(h);
    impl_->scene->fetchResults(true);
  }
}

Pose PhysXWorld::get_pose(int actor_id) const {
  if (actor_id < 0 || actor_id >= static_cast<int>(impl_->actors.size())) {
    throw std::out_of_range("PhysXWorld::get_pose invalid actor_id");
  }
  return from_px(impl_->actors[static_cast<size_t>(actor_id)]->getGlobalPose());
}

} // namespace nrtx
